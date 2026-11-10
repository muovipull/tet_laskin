import csv
import os
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Istuntojen salausavain

CSV_FILE = 'tyoajat.csv'
AUTH_FILE = 'auth.txt'
WORK_HOURS = 6.0  # Työpäivän pituus tunteina

# Alustetaan CSV-tiedosto, jos sitä ei ole
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Päivämäärä', 'Aloitus', 'Lopetus', 'Kesto (h)', 'Ylityö (h)'])

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Työajan seuranta</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 30px auto; padding: 20px; line-height: 1.6; background-color: #f9f9f9; }
        .card { background: white; border: 1px solid #ccc; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        button { background-color: #4CAF50; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; margin-right: 5px; font-size: 14px; }
        button.stop { background-color: #f44336; }
        button:hover { opacity: 0.9; }
        input[type="time"], input[type="password"] { padding: 8px; margin: 5px 0; width: 100%; box-sizing: border-box; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; background: white; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .alert { color: red; font-weight: bold; }
        a { color: #0066cc; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h2>Työajan seuranta</h2>
    
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        {% for message in messages %}
          <p class="alert">{{ message }}</p>
        {% endfor %}
      {% endif %}
    {% endwith %}

    {% if not is_registered %}
        <div class="card">
            <h3>Aseta salasana ensimmäisellä käyttökerralla</h3>
            <form method="POST" action="{{ url_for('register') }}">
                <label>Uusi salasana:</label>
                <input type="password" name="password" placeholder="Salasana" required><br><br>
                <button type="submit">Tallenna salasana</button>
            </form>
        </div>
    {% elif not logged_in %}
        <div class="card">
            <h3>Kirjaudu sisään</h3>
            <form method="POST" action="{{ url_for('login') }}">
                <label>Salasana:</label>
                <input type="password" name="password" placeholder="Salasana" required><br><br>
                <button type="submit">Kirjaudu</button>
            </form>
        </div>
    {% else %}
        <p><a href="{{ url_for('logout') }}">Kirjaudu ulos</a></p>
        
        <div class="card">
            <h3>Pikavalinnat</h3>
            <form method="POST" action="{{ url_for('quick_action') }}">
                <button type="submit" name="action" value="start">Aloita nyt</button>
                <button type="submit" name="action" value="stop" class="stop">Lopeta nyt</button>
            </form>
        </div>

        <div class="card">
            <h3>Kirjaa / Muokkaa työaikaa</h3>
            <form method="POST" action="{{ url_for('save_time') }}">
                <label>Aloitusaika:</label>
                <input type="time" name="start_time" value="{{ current_start }}" required><br>
                <label>Lopetusaika:</label>
                <input type="time" name="end_time" value="{{ current_end }}"><br><br>
                <button type="submit">Tallenna merkintä</button>
            </form>
            
            {% if calculated %}
                <h4>Päivän yhteenveto:</h4>
                <p><strong>Työaika:</strong> {{ duration }} tuntia</p>
                <p><strong>Ylityö / Alitus:</strong> {{ overtime }} tuntia</p>
                {% if target_leave %}
                    <p><strong>Suositeltu lähtöaika (6h työpäivä):</strong> {{ target_leave }}</p>
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
    
    start = session.get('start_time', '')
    end = session.get('end_time', '')
    
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
    now_str = datetime.now().strftime("%H:%M")
    
    if action == 'start':
        session['start_time'] = now_str
        session.pop('end_time', None)
    elif action == 'stop':
        session['end_time'] = now_str
        
    return redirect(url_for('index'))

@app.route('/save_time', methods=['POST'])
def save_time():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
        
    start = request.form.get('start_time')
    end = request.form.get('end_time')
    
    session['start_time'] = start
    session['end_time'] = end
    
    if start and end:
        try:
            t_start = datetime.strptime(start, "%H:%M")
            t_end = datetime.strptime(end, "%H:%M")
            diff = (t_end - t_start).total_seconds() / 3600.0
            if diff < 0:
                diff += 24
            overtime = diff - WORK_HOURS
            today = datetime.now().strftime("%Y-%m-%d")
            
            with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([today, start, end, f"{diff:.2f}", f"{overtime:+.2f}"])
                
            flash('Merkintä tallennettu CSV-tiedostoon.')
        except ValueError:
            flash('Virheellinen aika-arvo.')
            
    return redirect(url_for('index'))

if __name__ == '__main__':
    # host='0.0.0.0' mahdollistaa yhteydet avoimesta verkosta / muilta laitteilta verkossa
    app.run(host='0.0.0.0', port=6666, debug=False)