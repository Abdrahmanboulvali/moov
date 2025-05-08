from flask import Flask, render_template, request, redirect, url_for, session, flash
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
            session['user_id'] = user[0]
            return redirect(url_for('index'))
        else:
            if email == "admin@moov.com" and password == "adminmoov":
                session['adminmail'] = email
                return redirect(url_for('index_admin'))
            return render_template('se_connecter.html', error="Email ou mot de passe incorrect")

    return render_template('se_connecter.html')

@app.route('/se_deconnecter')
def se_deconnecter():
    session.clear()  # Supprime toutes les données de session
    return redirect(url_for('se_connecter'))  # Redirige vers la page de connexion

@app.route('/index')
def index():
    if 'usermail' not in session and 'adminmail' not in session:
        return redirect(url_for('se_connecter'))
    else:
        if 'adminmail' in session:
            return redirect(url_for('index_admin'))
    return render_template('index.html', usermail=session['usermail'])


@app.route('/index_admin')
def index_admin():
    if 'usermail' not in session and 'adminmail' not in session:
        return redirect(url_for('se_connecter'))
    else:
        if 'usermail' in session:
            return redirect(url_for('index'))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT total_reclamations, top_etats, top_entites, created_at
        FROM reclamation_summary
        ORDER BY created_at DESC
        LIMIT 1
    """)
    row = cur.fetchone()

    total = row[0] if row else 0
    top_etats = json.loads(row[1]) if row and row[1] else []
    top_entites = json.loads(row[2]) if row and row[2] else []
    created_at = row[3] if row else None

    cur.close()

    return render_template(
        'index_admin.html',
        adminmail=session['adminmail'],
        total=total,
        top_etats=top_etats,
        top_entites=top_entites,
        created_at=created_at
    )


@app.route('/utilisateurs')
def utilisateurs():
    if 'adminmail' not in session:
        return redirect(url_for('se_connecter'))
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, prenom, nom, sexe, email FROM utilisateurs")
    utilisateurs = cur.fetchall()
    cur.close()
    cur.close()
    return render_template('utilisateurs.html', utilisateurs=utilisateurs)

@app.route('/ajouter_utilisateur', methods=['GET', 'POST'])
def ajouter_utilisateur():
    if request.method == 'POST':
        prenom = request.form['prenom']
        nom = request.form['nom']
        sexe = request.form['sexe']
        email = request.form['email']
        mot_de_passe = request.form['mot_de_passe']

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO utilisateurs (prenom, nom, sexe, email, mot_de_passe) VALUES (%s, %s, %s, %s, %s)",
                       (prenom, nom, sexe, email, mot_de_passe))
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('utilisateurs'))

    return render_template('ajouter_utilisateur.html')

@app.route('/modifier_utilisateur_rec/<id>', methods=['GET'])
def modifier_utilisateur_rec(id):
    id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute("SELECT  * FROM utilisateurs WHERE id=%s", [id])
    utilisateur = cur.fetchone()
    cur.close()
    return render_template('modifier_utilisateur.html', utilisateur=utilisateur)

@app.route('/modifier_utilisateur/<int:id>', methods=['GET', 'POST'])
def modifier_utilisateur(id):
    cur = mysql.connection.cursor()


    cur.execute("SELECT * FROM utilisateurs WHERE id = %s", (id,))
    utilisateur = cur.fetchone()

    if not utilisateur:
        cur.close()
        return "Utilisateur non trouvé", 404

    if request.method == 'POST':
        prenom = request.form['prenom']
        nom = request.form['nom']
        sexe = request.form['sexe']
        email = request.form['email']
        password = request.form['password']

        if password != utilisateur[5]:
            cur.close()
            flash('Mot de passe incorrect. Veuillez réessayer.', 'danger')
            return redirect(request.url)
        cur.execute("""
            UPDATE utilisateurs 
            SET prenom=%s, nom=%s, sexe=%s, email=%s
            WHERE id=%s
        """, (prenom, nom, sexe, email, id))
        mysql.connection.commit()
        cur.close()
        flash("Modifications enregistrées avec succès.", "success")
        return redirect(url_for('profil'))

    cur.close()
    return render_template('modifier_utilisateur.html', utilisateur=utilisateur)

@app.route('/supprimer_utilisateur/<int:id>')
def supprimer_utilisateur(id):
    if 'adminmail' not in session:
        return redirect(url_for('se_connecter'))
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM utilisateurs WHERE id = %s", (id,))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('utilisateurs'))

@app.route('/profil', methods=['GET', 'POST'])
def profil():
    if 'user_id' not in session:
        return redirect(url_for('se_connecter'))

    id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM utilisateurs WHERE id = %s", [id])
    utilisateur = cur.fetchone()
    cur.close()

    return render_template('profil.html', utilisateur=utilisateur)

@app.route('/changer_mot_de_passe', methods=['GET', 'POST'])
def changer_mot_de_passe():
    if 'usermail' not in session:
        return redirect(url_for('se_connecter'))

    if request.method == 'POST':
        ancien = request.form['ancien']
        nouveau = request.form['nouveau']
        confirmation = request.form['confirmation']
        email = session['usermail']

        cur = mysql.connection.cursor()
        cur.execute("SELECT mot_de_passe FROM utilisateurs WHERE email = %s", [email])
        mot_de_passe_actuel = cur.fetchone()[0]

        if ancien != mot_de_passe_actuel:
            return render_template('changer_mot_de_passe.html', error="Ancien mot de passe incorrect.")
        if nouveau != confirmation:
            return render_template('changer_mot_de_passe.html', error="Les mots de passe ne correspondent pas.")

        cur.execute("UPDATE utilisateurs SET mot_de_passe = %s WHERE email = %s", (nouveau, email))
        mysql.connection.commit()
        cur.close()

        return render_template('changer_mot_de_passe.html', success="Mot de passe changé avec succès.")

    return render_template('changer_mot_de_passe.html')

@app.route('/statistiques')
def statistiques():
    if 'usermail' not in session and 'adminmail' not in session:
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

@app.route('/save_reclamation_summary')
def save_reclamation_summary():

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM reclamation_summary")

    cur.execute("SELECT COUNT(*) FROM reclamations")
    total_reclamations = cur.fetchone()[0]

    cur.execute("""
        SELECT etat_demande, COUNT(*) as count 
        FROM reclamations 
        GROUP BY etat_demande 
        ORDER BY count DESC 
        LIMIT 3
    """)
    top_etats = cur.fetchall()
    top_etats_json = json.dumps({etat: count for etat, count in top_etats})


    cur.execute("""
        SELECT entite, COUNT(*) as count 
        FROM reclamations 
        GROUP BY entite 
        ORDER BY count DESC 
        LIMIT 3
    """)
    top_entites = cur.fetchall()
    top_entites_json = json.dumps({entite: count for entite, count in top_entites})

    cur.execute("""
        INSERT INTO reclamation_summary (total_reclamations, top_etats, top_entites)
        VALUES (%s, %s, %s)
    """, (total_reclamations, top_etats_json, top_entites_json))

    mysql.connection.commit()
    cur.close()

    return redirect(url_for('index_admin'))

@app.route('/analyse_temporelle')
def analyse_temporelle():
    cur = mysql.connection.cursor()

    cur.execute("SELECT periode, total FROM reclamations_temporelles WHERE periode_type = 'mois' ORDER BY periode")
    data_mois = cur.fetchall()

    cur.execute("SELECT periode, total FROM reclamations_temporelles WHERE periode_type = 'annee' ORDER BY periode")
    data_annee = cur.fetchall()
    cur.close()

    labels_mois = [row[0] for row in data_mois]
    valeurs_mois = [row[1] for row in data_mois]

    labels_annee = [row[0] for row in data_annee]
    valeurs_annee = [row[1] for row in data_annee]

    return render_template(
        'analyse_temporelle.html',
        labels_mois=labels_mois,
        valeurs_mois=valeurs_mois,
        labels_annee=labels_annee,
        valeurs_annee=valeurs_annee
    )

@app.route('/update_stats_temporelles')
def update_stats_temporelles():
    cur = mysql.connection.cursor()

    # Vider les anciennes données
    cur.execute("DELETE FROM reclamations_temporelles")

    # Insérer les données mensuelles
    cur.execute("""
        INSERT INTO reclamations_temporelles (periode_type, periode, total)
        SELECT 'mois', DATE_FORMAT(date_saisie, '%Y-%m'), COUNT(*)
        FROM reclamations
        WHERE date_saisie IS NOT NULL
        GROUP BY DATE_FORMAT(date_saisie, '%Y-%m')
    """)

    # Insérer les données annuelles
    cur.execute("""
        INSERT INTO reclamations_temporelles (periode_type, periode, total)
        SELECT 'annee', DATE_FORMAT(date_saisie, '%Y'), COUNT(*)
        FROM reclamations
        WHERE date_saisie IS NOT NULL
        GROUP BY DATE_FORMAT(date_saisie, '%Y')
    """)

    mysql.connection.commit()
    cur.close()
    return redirect(url_for('analyse_temporelle'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
