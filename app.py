from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import json
from collections import defaultdict
from datetime import datetime, timedelta

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
        login = request.form['userlogin']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM utilisateurs WHERE login = %s AND mot_de_passe = %s", (login, password))
        user = cur.fetchone()
        cur.close()

        if user:
            if user[6] == "agent":
                session['userlogin'] = login
                session['user_id'] = user[0]
                return redirect(url_for('index'))
            elif user[6] == "admin":
                session['adminlogin'] = login
                session['user_id'] = user[0]
                return redirect(url_for('index_admin'))
        else:
            return render_template('se_connecter.html', error="Login ou mot de passe incorrect")

    return render_template('se_connecter.html')

@app.route('/se_deconnecter')
def se_deconnecter():
    session.clear()  # Supprime toutes les données de session
    return redirect(url_for('se_connecter'))  # Redirige vers la page de connexion

@app.route('/index')
def index():
    if 'userlogin' not in session and 'adminlogin' not in session:
        return redirect(url_for('se_connecter'))
    else:
        if 'adminlogin' in session:
            return redirect(url_for('index_admin'))
    login = session['userlogin']
    cur = mysql.connection.cursor()
    cur.execute("SELECT numero, objet, canal, date_saisie, date_ext, etat_demande FROM reclamations WHERE login = %s",
                (login,))
    reclamations = cur.fetchall()
    cur.close()

    return render_template('index.html', reclamations=reclamations)

@app.route('/index_admin')
def index_admin():
    if 'userlogin' not in session and 'adminlogin' not in session:
        return redirect(url_for('se_connecter'))
    else:
        if 'userlogin' in session:
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
        adminlogin=session['adminlogin'],
        total=total,
        top_etats=top_etats,
        top_entites=top_entites,
        created_at=created_at
    )


@app.route('/utilisateurs')
def utilisateurs():
    if 'adminlogin' not in session:
        return redirect(url_for('se_connecter'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT u.id, u.prenom, u.nom, u.sexe, u.login, u.role, a.nom_agence
        FROM utilisateurs u
        LEFT JOIN agences a ON u.agence_id = a.id
    """)
    utilisateurs = cur.fetchall()
    cur.close()

    return render_template('utilisateurs.html', utilisateurs=utilisateurs)

@app.route('/ajouter_utilisateur', methods=['GET', 'POST'])
def ajouter_utilisateur():
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        prenom = request.form['prenom']
        nom = request.form['nom']
        sexe = request.form['sexe']
        login = request.form['login']
        mot_de_passe = request.form['mot_de_passe']
        agence_id = request.form['agence_id']
        role = request.form['role']

        cur.execute("""
            INSERT INTO utilisateurs (prenom, nom, sexe, login, mot_de_passe, role, agence_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (prenom, nom, sexe, login, mot_de_passe, role, agence_id))

        mysql.connection.commit()
        cur.close()

        return redirect(url_for('utilisateurs'))


    cur.execute("SELECT id, nom_agence FROM agences")
    agences = cur.fetchall()
    cur.close()

    return render_template("ajouter_utilisateur.html", agences=agences)


@app.route('/agences')
def agences():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM agences")
    agences = cur.fetchall()
    cur.close()
    return render_template('agences.html', agences=agences)

@app.route('/ajouter_agence', methods=['GET', 'POST'])
def ajouter_agence():
    if request.method == 'POST':
        nom_agence = request.form['nom_agence']
        localisation = request.form['localisation']

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO agences (nom_agence, localisation) VALUES (%s, %s)", (nom_agence, localisation))
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('agences'))
    return render_template('ajouter_agence.html')

@app.route('/modifier_agence/<int:id>', methods=['GET', 'POST'])
def modifier_agence(id):
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        nom_agence = request.form['nom_agence']
        localisation = request.form['localisation']
        cur.execute("UPDATE agences SET nom_agence = %s, localisation = %s WHERE id = %s", (nom_agence, localisation, id))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('agences'))

    # Sinon (GET), afficher les infos existantes
    cur.execute("SELECT * FROM agences WHERE id = %s", (id,))
    agence = cur.fetchone()
    cur.close()

    if not agence:
        return "Agence non trouvée", 404

    return render_template('modifier_agence.html', agence=agence)

@app.route('/supprimer_agence/<int:id>')
def supprimer_agence(id):
    if 'adminlogin' not in session:
        return redirect(url_for('se_connecter'))
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM agences WHERE id = %s", (id,))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('agences'))


@app.route('/agence/<int:agence_id>/utilisateurs')
def utilisateurs_par_agence(agence_id):
    if 'adminlogin' not in session:
        return redirect(url_for('se_connecter'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT u.id, u.prenom, u.nom, u.sexe, u.login, a.nom_agence
        FROM utilisateurs u
        JOIN agences a ON u.agence_id = a.id
        WHERE a.id = %s
    """, (agence_id,))
    utilisateurs = cur.fetchall()

    cur.execute("SELECT nom_agence FROM agences WHERE id = %s", (agence_id,))
    agence_nom = cur.fetchone()[0]

    cur.close()
    return render_template('utilisateurs_par_agence.html', utilisateurs=utilisateurs, agence_nom=agence_nom)


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
        login = request.form['login']
        password = request.form['password']

        if password != utilisateur[4]:
            cur.close()
            flash('Mot de passe incorrect. Veuillez réessayer.', 'danger')
            return redirect(request.url)
        cur.execute("""
            UPDATE utilisateurs 
            SET prenom=%s, nom=%s, sexe=%s, login=%s
            WHERE id=%s
        """, (prenom, nom, sexe, login, id))
        mysql.connection.commit()
        cur.close()
        flash("Modifications enregistrées avec succès.", "success")
        return redirect(url_for('profil'))

    cur.close()
    return render_template('modifier_utilisateur.html', utilisateur=utilisateur)


@app.route('/supprimer_utilisateur/<int:id>')
def supprimer_utilisateur(id):
    if 'adminlogin' not in session:
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
    if 'userlogin' not in session and 'adminlogin' not in session:
        return redirect(url_for('se_connecter'))
    user_id = session['user_id']

    if request.method == 'POST':
        ancien = request.form['ancien']
        nouveau = request.form['nouveau']
        confirmation = request.form['confirmation']
        if 'userlogin' in session:
            login = session['userlogin']
        if 'adminlogin' in session:
            login = session['adminlogin']

        cur = mysql.connection.cursor()
        cur.execute("SELECT mot_de_passe FROM utilisateurs WHERE id = %s", [user_id])
        mot_de_passe_actuel = cur.fetchone()

        if not mot_de_passe_actuel or ancien != mot_de_passe_actuel[0]:
            return render_template('changer_mot_de_passe.html', error="Ancien mot de passe incorrect.")
        if nouveau != confirmation:
            return render_template('changer_mot_de_passe.html', error="Les mots de passe ne correspondent pas.")

        cur.execute("UPDATE utilisateurs SET mot_de_passe = %s WHERE login = %s", (nouveau, login))
        mysql.connection.commit()
        cur.close()

        return render_template('changer_mot_de_passe.html', success="Mot de passe changé avec succès.")

    return render_template('changer_mot_de_passe.html')

@app.route('/ajouter', methods=['GET', 'POST'])
def ajouter():
    if request.method == 'POST':
        numero = request.form['numero']
        canal = request.form['canal']
        objet = request.form['objet']
        login = request.form['login']
        etat_demande = request.form['etat_demande']
        cause_reclamation = request.form['cause_reclamation']
        contact = request.form['contact']

        date_saisie = request.form['date_saisie'] if request.form['date_saisie'] else datetime.now().strftime(
            '%Y-%m-%d %H:%M:%S')


        date_ext = request.form['date_ext'] if request.form['date_ext'] else '2040-01-01 00:00:00'

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO reclamations (numero, canal, objet, login, etat_demande, cause_reclamation, contact, date_saisie, date_ext) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (numero, canal, objet, login, etat_demande, cause_reclamation, contact, date_saisie, date_ext))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('index'))

    # Pour GET
    cur = mysql.connection.cursor()
    cur.execute("SELECT DISTINCT canal FROM reclamations")
    canaux = [row[0] for row in cur.fetchall()]
    cur.close()
    return render_template('ajouter.html', canaux=canaux)


@app.route('/modifier_reclamation/<string:numero>', methods=['GET', 'POST'])
def modifier_reclamation(numero):
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        objet = request.form['objet']
        canal = request.form['canal']
        date_saisie = request.form['date_saisie']
        date_cloture = request.form['date_cloture']
        etat = request.form['etat']

        cur.execute("""
            UPDATE reclamations 
            SET objet = %s, canal = %s, date_saisie = %s, date_ext = %s, etat_demande = %s 
            WHERE numero = %s
        """, (objet, canal, date_saisie, date_cloture, etat, numero))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('index'))

    cur.execute("SELECT * FROM reclamations WHERE numero = %s", (numero,))
    reclamation = cur.fetchone()
    cur.close()

    if not reclamation:
        return "Réclamation non trouvée", 404

    return render_template('modifier_reclamation.html', reclamation=reclamation)


@app.route('/supprimer_reclamation/<string:numero>')
def supprimer_reclamation(numero):
    if 'userlogin' not in session:
        return redirect(url_for('se_connecter'))
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM reclamations WHERE numero = %s", (numero,))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('index'))

@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    if value is None:
        return ""
    if isinstance(value, str):
        value = datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    return value.strftime(format)


@app.route('/statistiques')
def statistiques():
    if 'userlogin' not in session and 'adminlogin' not in session:
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

    # Données quotidiennes
    cur.execute("SELECT periode, total FROM reclamations_temporelles WHERE periode_type = 'jour' ORDER BY periode")
    data_jour = cur.fetchall()

    # Données mensuelles
    cur.execute("SELECT periode, total FROM reclamations_temporelles WHERE periode_type = 'mois' ORDER BY periode")
    data_mois = cur.fetchall()

    # Données annuelles
    cur.execute("SELECT periode, total FROM reclamations_temporelles WHERE periode_type = 'annee' ORDER BY periode")
    data_annee = cur.fetchall()

    # Données des dernières 48 heures globales
    cur.execute("""
        SELECT DATE_FORMAT(date_saisie, '%Y-%m-%d %H:00:00') AS heure, COUNT(*) AS total
        FROM reclamations
        WHERE date_saisie >= NOW() - INTERVAL 48 HOUR
        GROUP BY heure
        ORDER BY heure
    """)
    data_48h = cur.fetchall()

    # Réclamations individuelles pour le tableau
    cur.execute("""
    SELECT r.*, u.prenom, u.nom, u.login
    FROM reclamations r
    LEFT JOIN utilisateurs u ON r.login = u.login
    WHERE r.date_saisie >= NOW() - INTERVAL 48 HOUR
    """)
    reclamations_48h = cur.fetchall()

    # Réclamations pour état et canal sur 48h
    cur.execute("""
        SELECT DATE_FORMAT(date_saisie, '%Y-%m-%d %H:00:00') AS heure, etat_demande, canal, COUNT(*) as total
        FROM reclamations
        WHERE date_saisie >= NOW() - INTERVAL 48 HOUR
        GROUP BY heure, etat_demande, canal
        ORDER BY heure
    """)
    grouped_48h = cur.fetchall()


    maintenant = datetime.now()
    heures = [(maintenant - timedelta(hours=i)).strftime('%Y-%m-%d %H:00:00') for i in reversed(range(49))]

    # Préparation des structures
    data_par_etat = defaultdict(lambda: defaultdict(int))
    data_par_canal = defaultdict(lambda: defaultdict(int))

    for heure, etat, canal, total in grouped_48h:
        data_par_etat[etat][heure] += total
        data_par_canal[canal][heure] += total

    datasets_48h_etat = []
    for etat, valeurs in data_par_etat.items():
        datasets_48h_etat.append({
            "label": f"État : {etat}",
            "data": [valeurs.get(h, 0) for h in heures],
            "borderColor": "rgba(54, 162, 235, 0.8)",
            "backgroundColor": "rgba(54, 162, 235, 0.1)",
            "fill": True,
            "tension": 0.4
        })

    datasets_48h_canal = []
    for canal, valeurs in data_par_canal.items():
        datasets_48h_canal.append({
            "label": f"Canal : {canal}",
            "data": [valeurs.get(h, 0) for h in heures],
            "borderColor": "rgba(255, 99, 132, 0.8)",
            "backgroundColor": "rgba(255, 99, 132, 0.1)",
            "fill": True,
            "tension": 0.4
        })

    # Réclamations pour utilisateur (login) sur 48h
    cur.execute("""
        SELECT DATE_FORMAT(date_saisie, '%Y-%m-%d %H:00:00') AS heure, login, COUNT(*) as total
        FROM reclamations
        WHERE date_saisie >= NOW() - INTERVAL 48 HOUR
        GROUP BY heure, login
        ORDER BY heure
    """)
    grouped_48h_login = cur.fetchall()

    # Préparation des structures pour login
    data_par_login = defaultdict(lambda: defaultdict(int))
    for heure, login, total in grouped_48h_login:
        data_par_login[login][heure] += total

    datasets_48h_login = []
    for login, valeurs in data_par_login.items():
        datasets_48h_login.append({
            "label": f"Utilisateur : {login}",
            "data": [valeurs.get(h, 0) for h in heures],
            "borderColor": f"rgba({hash(login) % 255}, {(hash(login) // 255) % 255}, {(hash(login) // 65025) % 255}, 0.8)",
            "backgroundColor": f"rgba({hash(login) % 255}, {(hash(login) // 255) % 255}, {(hash(login) // 65025) % 255}, 0.1)",
            "fill": True,
            "tension": 0.4
        })

    cur.close()

    return render_template(
        'analyse_temporelle.html',
        labels_jour=[row[0] for row in data_jour],
        valeurs_jour=[row[1] for row in data_jour],
        labels_mois=[row[0] for row in data_mois],
        valeurs_mois=[row[1] for row in data_mois],
        labels_annee=[row[0] for row in data_annee],
        valeurs_annee=[row[1] for row in data_annee],
        reclamations_48h=reclamations_48h,
        labels_48h=[row[0] for row in data_48h],
        valeurs_48h=[row[1] for row in data_48h],
        labels_48h_etat=heures,
        datasets_48h_etat=datasets_48h_etat,
        labels_48h_canal=heures,
        datasets_48h_canal=datasets_48h_canal,
        labels_48h_login = heures,
        datasets_48h_login = datasets_48h_login

    )



@app.route('/update_stats_temporelles')
def update_stats_temporelles():
    cur = mysql.connection.cursor()

    # Vider les anciennes données
    cur.execute("DELETE FROM reclamations_temporelles")

    # Insérer les données par jour
    cur.execute("""
        INSERT INTO reclamations_temporelles (periode_type, periode, total)
        SELECT 'jour', DATE_FORMAT(date_saisie, '%Y-%m-%d'), COUNT(*)
        FROM reclamations
        WHERE date_saisie IS NOT NULL
        GROUP BY DATE_FORMAT(date_saisie, '%Y-%m-%d')
    """)
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
