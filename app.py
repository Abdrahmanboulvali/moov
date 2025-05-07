from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import json

app = Flask(__name__)

# Configuration MySQL
app.secret_key ="moov_moritel"
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'GDR_bd'

mysql = MySQL(app)


@app.route('/', methods=['GET', 'POST'])
def se_connecter():
    if request.method == 'POST':
        email = request.form['usermail']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM utilisateurs WHERE email = %s AND mot_de_passe = %s", (email, password))
        user = cur.fetchone()
        cur.close()

        if user:
            session['usermail'] = email
            return redirect(url_for('index'))
        else:
            return render_template('se_connecter.html', error="Email ou mot de passe incorrect")

    return render_template('se_connecter.html')

@app.route('/se_deconnecter')
def se_deconnecter():
    session.clear()  # Supprime toutes les données de session
    return redirect(url_for('se_connecter'))  # Redirige vers la page de connexion

@app.route('/index')
def index():
    if 'usermail' not in session:
        return redirect(url_for('se_connecter'))
    return render_template('index.html', usermail=session['usermail'])

@app.route('/statistiques')
def statistiques():
    if 'usermail' not in session:
        return redirect(url_for('se_connecter'))
    cur = mysql.connection.cursor()

    # Lire les données enregistrées (une seule ligne)
    cur.execute("SELECT etat_demande_percent, entite_percent, objet_percent, canal_percent FROM statistics_data LIMIT 1")
    existing_data = cur.fetchone()

    if existing_data and all(existing_data):
        # Charger les données depuis la base
        data_etat = json.loads(existing_data[0])
        data_entite = json.loads(existing_data[1])
        data_objet = json.loads(existing_data[2])
        data_canal = json.loads(existing_data[3])

        labels_etat = list(data_etat.keys())
        values_etat = list(data_etat.values())

        labels_entite = list(data_entite.keys())
        values_entite = list(data_entite.values())

        labels_objet = list(data_objet.keys())
        values_objet = list(data_objet.values())

        labels_canal = list(data_canal.keys())
        values_canal = list(data_canal.values())
    else:
        # Recalculer et sauvegarder
        cur.execute("SELECT etat_demande, COUNT(*) FROM reclamations GROUP BY etat_demande")
        data_etat_raw = cur.fetchall()
        total_etat = sum(row[1] for row in data_etat_raw)
        data_etat = {row[0]: round(row[1]*100/total_etat, 2) for row in data_etat_raw}

        cur.execute("SELECT entite, COUNT(*) FROM reclamations GROUP BY entite ORDER BY COUNT(*) DESC LIMIT 10")
        data_entite_raw = cur.fetchall()
        total_entite = sum(row[1] for row in data_entite_raw)
        data_entite = {row[0]: round(row[1]*100/total_entite, 2) for row in data_entite_raw}

        cur.execute("SELECT objet, COUNT(*) FROM reclamations GROUP BY objet ORDER BY COUNT(*) DESC LIMIT 10")
        data_objet_raw = cur.fetchall()
        total_objet = sum(row[1] for row in data_objet_raw)
        data_objet = {row[0]: round(row[1]*100/total_objet, 2) for row in data_objet_raw}

        cur.execute("SELECT canal, COUNT(*) FROM reclamations GROUP BY canal")
        data_canal_raw = cur.fetchall()
        total_canal = sum(row[1] for row in data_canal_raw)
        data_canal = {row[0]: round(row[1]*100/total_canal, 2) for row in data_canal_raw}

        # Sauvegarder une seule fois
        cur.execute("""
            INSERT INTO statistics_data (etat_demande_percent, entite_percent, objet_percent, canal_percent)
            VALUES (%s, %s, %s, %s)
        """, (
            json.dumps(data_etat),
            json.dumps(data_entite),
            json.dumps(data_objet),
            json.dumps(data_canal)
        ))
        mysql.connection.commit()

        labels_etat = list(data_etat.keys())
        values_etat = list(data_etat.values())

        labels_entite = list(data_entite.keys())
        values_entite = list(data_entite.values())

        labels_objet = list(data_objet.keys())
        values_objet = list(data_objet.values())

        labels_canal = list(data_canal.keys())
        values_canal = list(data_canal.values())

    cur.close()

    return render_template("statistiques.html",
                           labels_etat=labels_etat, data_etat=values_etat,
                           labels_entite=labels_entite, data_entite=values_entite,
                           labels_objet=labels_objet, data_objet=values_objet,
                           labels_canal=labels_canal, data_canal=values_canal)

@app.route('/mettre_a_jour_statistiques', methods=['POST'])
def mettre_a_jour_statistiques():
    cur = mysql.connection.cursor()

    cur.execute("DELETE FROM statistics_data")

    cur.execute("SELECT etat_demande, COUNT(*) FROM reclamations GROUP BY etat_demande")
    data_etat_raw = cur.fetchall()
    total_etat = sum(row[1] for row in data_etat_raw)
    data_etat = {row[0]: round(row[1]*100/total_etat, 2) for row in data_etat_raw}

    cur.execute("SELECT entite, COUNT(*) FROM reclamations GROUP BY entite ORDER BY COUNT(*) DESC LIMIT 10")
    data_entite_raw = cur.fetchall()
    total_entite = sum(row[1] for row in data_entite_raw)
    data_entite = {row[0]: round(row[1]*100/total_entite, 2) for row in data_entite_raw}

    cur.execute("SELECT objet, COUNT(*) FROM reclamations GROUP BY objet ORDER BY COUNT(*) DESC LIMIT 10")
    data_objet_raw = cur.fetchall()
    total_objet = sum(row[1] for row in data_objet_raw)
    data_objet = {row[0]: round(row[1]*100/total_objet, 2) for row in data_objet_raw}

    cur.execute("SELECT canal, COUNT(*) FROM reclamations GROUP BY canal")
    data_canal_raw = cur.fetchall()
    total_canal = sum(row[1] for row in data_canal_raw)
    data_canal = {row[0]: round(row[1]*100/total_canal, 2) for row in data_canal_raw}

    # Enregistrer
    cur.execute("""
        INSERT INTO statistics_data (etat_demande_percent, entite_percent, objet_percent, canal_percent)
        VALUES (%s, %s, %s, %s)
    """, (
        json.dumps(data_etat),
        json.dumps(data_entite),
        json.dumps(data_objet),
        json.dumps(data_canal)
    ))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('statistiques'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
