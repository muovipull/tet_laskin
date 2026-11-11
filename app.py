import csv
import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)

CSV_FILE = 'tyoajat.csv'
AUTH_FILE = 'auth.txt'
STATE_FILE = 'state.json'
WORK_HOURS = 6.0  # Työpäivän pituus tunteina
FIN_TZ = ZoneInfo("Europe/Helsinki")

# Alustetaan CSV-tiedosto, jos sitä ei ole
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Päivämäärä', 'Aloitus', 'Lopetus', 'Kesto (h)', 'Ylityö (h)'])

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Työajan seuranta</title>
    <style>
        :root {
            --primary: #4f46e5;
            --primary-hover: #4338ca;
            --danger: #dc2626;
            --danger-hover: #b91c1c;
            --bg: #f3f4f6;
            --card-bg: #ffffff;
            --text: #1f2937;
            --border: #e5e7eb;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            max-width: 650px;
            margin: 40px auto;
            padding: 20px;
            line-height: 1.5;
        }
        h2, h3, h4 { color: #111827; margin-top: 0; }
        .header-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        }
        .btn {
            background-color: var(--primary);
            color: white;
            padding: 10px 18px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 15px;
            font-weight: 600;
            transition: background-color 0.2s;
            display: inline-block;
            text-decoration: none;
        }
        .btn:hover { background-color: var(--primary-hover); }
        .btn-stop { background-color: var(--danger); }
        .btn-stop:hover { background-color: var(--danger-hover); }
        .btn-secondary { background-color: #6b7280; }
        .btn-secondary:hover { background-color: #4b5563; }
        
        input[type="time"], input[type="password"] {
            padding: 10px;
            margin: 8px 0 16px 0;
            width: 100%;
            box-sizing: border-box;
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 15px;
        }
        label { font-weight: 600; font-size: 14px; color: #4b5563; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
        }
        th, td { border-bottom: 1px solid var(--border); padding: 12px; text-align: left; font-size: 14px; }
        th { background-color: #f9fafb; font-weight: 600; }
        tr:last-child td { border-bottom: none; }
        .alert {
            background-color: #fee2e2;
            color: #991b1b;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
            font-weight: 500;
            border: 1px solid #f87171;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            background-color: #d1fae5;
            color: #065f46;
            margin-bottom: 15px;
        }
        .logout-link { color: #6b7280; font-size: 14px; text-decoration: none; }
        .logout-link:hover { text-decoration: underline; color: var(--text); }
    </style>
</head>
<body>
    <div class="header-bar">
        <h2>Työajan seuranta</h2>
        {% if logged_in %}
            <a href="{{ url_for('logout') }}" class="logout-link">Kirjaudu ulos</a>
        {% endif %}
    </div>
    
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        {% for message in messages %}
          <div class="alert">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    {% if not is_registered %}
        <div class="card">
            <h3>Aseta salasana ensimmäisellä käyttökerralla</h3>
            <form method="POST" action="{{ url_for('register') }}">
                <label>Uusi salasana:</label>
                <input type="password" name="password" placeholder="Salasana" required>
                <button type="submit" class="btn">Tallenna salasana</button>
            </form>
        </div>
    {% elif not logged_in %}
        <div class="card">
            <h3>Kirjaudu sisään</h3>
            <form method="POST" action="{{ url_for('login') }}">
                <label>Salasana:</label>
                <input type="password" name="password" placeholder="Salasana" required>
                <button type="submit" class="btn">Kirjaudu</button>
            </form>
        </div>
    {% else %}
        
        <div class="card">
            <h3>Pikavalinnat</h3>
            {% if current_start %}
                <div class="status-badge">Työvuoro käynnissä klo {{ current_start }} alkaen</div>
            {% endif %}
            <form method="POST" action="{{ url_for('quick_action') }}" style="display: flex; gap: 10px;">
                <button type="submit" name="action" value="start" class="btn">Aloita nyt</button>
                <button type="submit" name="action" value="stop" class="btn btn-stop">Lopeta nyt</button>
            </form>
        </div>

        <div class="card">
            <h3>Kirjaa / Muokkaa työaikaa</h3>
            <form method="POST" action="{{ url_for('save_time') }}">
                <label>Aloitusaika:</label>
                <input type="time" name="start_time" value="{{ current_start }}" required>
                
                <label>Lopetusaika:</label>
                <input type="time" name="end_time" value="{{ current_end }}">
                
                <button type="submit" class="btn btn-secondary">Tallenna merkintä CSV:hen</button>
            </form>
            
            {% if calculated %}
                <hr style="border:0; border-top:1px solid var(--border); margin: 20px 0;">
                <h4>Päivän yhteenveto:</h4>
                <p><strong>Työaika:</strong> {{ duration }} tuntia</p>
                <p><strong>Ylityö / Alitus (6h tavoite):</strong> {{ overtime }} tuntia</p>
                {% if target_leave %}
                    <p><strong>Suositeltu lähtöaika:</strong> {{ target_leave }}</p>
                {% endif %}
            {% endif %}
        </div>

        <div class="card">
            <h3>Tallennetut työajat</h3>
            <table>
                <tr>
                    <th>Pvm</th>
                    <th>Aloitus</th>
                    <th>Lopetus</th>
                    <th>Kesto (h)</th>
                    <th>Ylityö (h)</th>
                </tr>
                {% for row in logs %}
                <tr>
                    <td>{{ row[0] }}</td>
                    <td>{{ row[1] }}</td>
                    <td>{{ row[2] }}</td>
                    <td>{{ row[3] }}</td>
                    <td>{{ row[4] }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
    {% endif %}
</body>
</html>
"""

def is_registered():
    return os.path.exists(AUTH_FILE)

def check_password(password):
    if not is_registered():
        return False
    with open(AUTH_FILE, 'r') as f:
        stored_hash = f.read().strip()
    return check_password_hash(stored_hash, password)

def get_logs():
    logs = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # Ohitetaan otsikko
            logs = list(reader)
    return logs

@app.route('/')
def index():
    reg = is_registered()
    logged = session.get('logged_in', False)
    logs = get_logs() if logged else []
    
    state = load_state()
    start = state.get('start_time', '')
    end = state.get('end_time', '')
    
    calculated = False
    duration_str = ""
    overtime_str = ""
    target_leave = ""

    if start:
        try:
            t_start = datetime.strptime(start, "%H:%M")
            t_target = t_start + timedelta(hours=WORK_HOURS)
            target_leave = t_target.strftime("%H:%M")
            
            if end:
                t_end = datetime.strptime(end, "%H:%M")
                diff = (t_end - t_start).total_seconds() / 3600.0
                if diff < 0:
                    diff += 24  # Yön yli menevät vuorot
                
                overtime = diff - WORK_HOURS
                duration_str = f"{diff:.2f}"
                overtime_str = f"{overtime:+.2f}"
                calculated = True
        except ValueError:
            pass

    return render_template_string(
        HTML_TEMPLATE, 
        is_registered=reg, 
        logged_in=logged,
        current_start=start,
        current_end=end,
        calculated=calculated,
        duration=duration_str,
        overtime=overtime_str,
        target_leave=target_leave,
        logs=reversed(logs)
    )

@app.route('/register', methods=['POST'])
def register():
    if not is_registered():
        pwd = request.form.get('password')
        if pwd:
            hashed = generate_password_hash(pwd)
            with open(AUTH_FILE, 'w') as f:
                f.write(hashed)
            session['logged_in'] = True
    return redirect(url_for('index'))

@app.route('/login', methods=['POST'])
def login():
    pwd = request.form.get('password')
    if check_password(pwd):
        session['logged_in'] = True
    else:
        flash('Väärä salasana!')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/quick_action', methods=['POST'])
def quick_action():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
        
    action = request.form.get('action')
    now = datetime.now(FIN_TZ)
    now_str = now.strftime("%H:%M")
    today_str = now.strftime("%Y-%m-%d")
    
    state = load_state()
    
    if action == 'start':
        state = {'start_date': today_str, 'start_time': now_str, 'end_time': ''}
        save_state(state)
        flash('Työaika aloitettu klo ' + now_str)
    elif action == 'stop':
        if not state.get('start_time'):
            flash('Aloita ensin työaika!')
        else:
            state['end_time'] = now_str
            save_state(state)
            
            # Tallennetaan automaattisesti CSV-tiedostoon kun lopetetaan napista
            start = state.get('start_time')
            end = now_str
            try:
                t_start = datetime.strptime(start, "%H:%M")
                t_end = datetime.strptime(end, "%H:%M")
                diff = (t_end - t_start).total_seconds() / 3600.0
                if diff < 0:
                    diff += 24
                overtime = diff - WORK_HOURS
                
                with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([today_str, start, end, f"{diff:.2f}", f"{overtime:+.2f}"])
                
                flash('Työvuoro tallennettu CSV-tiedostoon!')
                # Tyhjennetään aktiivinen tila tallennuksen jälkeen
                if os.path.exists(STATE_FILE):
                    os.remove(STATE_FILE)
            except ValueError:
                flash('Virheellinen aika-arvo.')
                
    return redirect(url_for('index'))

@app.route('/save_time', methods=['POST'])
def save_time():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
        
    start = request.form.get('start_time')
    end = request.form.get('end_time')
    
    state = load_state()
    state['start_time'] = start
    state['end_time'] = end
    save_state(state)
    
    if start and end:
        try:
            t_start = datetime.strptime(start, "%H:%M")
            t_end = datetime.strptime(end, "%H:%M")
            diff = (t_end - t_start).total_seconds() / 3600.0
            if diff < 0:
                diff += 24
            overtime = diff - WORK_HOURS
            today = datetime.now(FIN_TZ).strftime("%Y-%m-%d")
            
            with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([today, start, end, f"{diff:.2f}", f"{overtime:+.2f}"])
                
            flash('Manuaalinen merkintä tallennettu CSV-tiedostoon.')
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
        except ValueError:
            flash('Virheellinen aika-arvo.')
            
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6666, debug=False)