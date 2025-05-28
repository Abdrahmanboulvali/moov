from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
import json
from collections import defaultdict
from datetime import datetime, timedelta
from MySQLdb.cursors import DictCursor

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
    cur.execute("SELECT numero, objet, canal, date_saisie, date_ext, etat_demande, id FROM reclamations WHERE login = %s",
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
    session.pop('previous_page', None)
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

    if request.method == 'GET' and 'previous_page' not in session:
        session['previous_page'] = request.referrer
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT u.id, u.prenom, u.nom, u.sexe, u.login, u.role, u.est_chef_agence, a.nom_agence
        FROM utilisateurs u
        JOIN agences a ON u.agence_id = a.id
        WHERE a.id = %s
    """, (agence_id,))
    utilisateurs = cur.fetchall()

    cur.execute("SELECT nom_agence FROM agences WHERE id = %s", (agence_id,))
    agence_nom = cur.fetchone()[0]

    cur.close()
    return render_template('utilisateurs_par_agence.html', utilisateurs=utilisateurs, agence_nom=agence_nom, agence_id=agence_id)


@app.route('/definir_chef_agence/<int:user_id>/<int:agence_id>')
def definir_chef_agence(user_id, agence_id):
    if 'adminlogin' not in session:
        return redirect(url_for('se_connecter'))

    cur = mysql.connection.cursor()

    cur.execute("SELECT role FROM utilisateurs WHERE id = %s", (user_id,))
    result = cur.fetchone()
    if not result:
        flash("Utilisateur introuvable", "danger")
        return redirect(url_for('utilisateurs_par_agence', agence_id=agence_id))

    role = result[0]
    if role == 'admin':
        flash("Impossible de définir un administrateur comme chef d'agence.", "warning")
        return redirect(url_for('utilisateurs_par_agence', agence_id=agence_id))

    cur.execute("UPDATE utilisateurs SET est_chef_agence = 0 WHERE agence_id = %s", (agence_id,))

    cur.execute("UPDATE utilisateurs SET est_chef_agence = 1 WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cur.close()

    flash("Chef d'agence défini avec succès.", "success")
    return redirect(url_for('utilisateurs_par_agence', agence_id=agence_id))

@app.route('/utilisateur/<int:user_id>/modifier', methods=['GET', 'POST'])
def modifier_utilisateur_admin(user_id):
    if 'adminlogin' not in session:
        return redirect(url_for('se_connecter'))

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        agence_id = request.form['agence_id']
        role = request.form['role']

        cur.execute("""
            UPDATE utilisateurs
            SET agence_id = %s, role = %s
            WHERE id = %s
        """, (agence_id, role, user_id))
        mysql.connection.commit()
        cur.close()
        flash("Utilisateur modifié avec succès.")
        return redirect(url_for('utilisateurs_par_agence', agence_id=agence_id))

    # GET: afficher formulaire
    cur.execute("SELECT * FROM utilisateurs WHERE id = %s", (user_id,))
    utilisateur = cur.fetchone()

    cur.execute("SELECT id, nom_agence FROM agences")
    agences = cur.fetchall()

    cur.close()
    return render_template('modifier_utilisateur_admin.html', utilisateur=utilisateur, agences=agences)


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
        sous_reclamation = request.form.get('sous_reclamation', '')
        login = request.form['login']
        cause_reclamation = request.form['cause_reclamation']
        contact = request.form['contact']
        etat_demande = request.form.get('etat_demande')
        if not etat_demande:
            etat_demande = "Clôturé N0"

        date_saisie = datetime.now()


        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT libelle, delai, etat
            FROM structure_gdr
            WHERE arborescence = %s
        """, (sous_reclamation,))
        row = cur.fetchone()

        if row:
            objet_libelle = row[0]
            delai_jours = row[1] or 0
            etat_demande_auto = row[2] or ''
        else:
            objet_libelle = sous_reclamation
            delai_jours = 0
            etat_demande_auto = ''


        date_pre_vid = date_saisie + timedelta(days=delai_jours)


        date_ext_str = request.form['date_ext']
        if date_ext_str:
            date_ext = datetime.strptime(date_ext_str, '%Y-%m-%dT%H:%M')
        else:
            date_ext = datetime(2040, 1, 1)


        cur.execute("""
            INSERT INTO reclamations
            (numero, canal, objet, login, etat_demande, cause_reclamation, contact, date_saisie, date_prevue_vid, date_ext)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            numero, canal, objet_libelle, login, etat_demande, cause_reclamation, contact,
            date_saisie.strftime('%Y-%m-%d %H:%M:%S'),
            date_pre_vid.strftime('%Y-%m-%d %H:%M:%S'),
            date_ext.strftime('%Y-%m-%d %H:%M:%S')
        ))

        mysql.connection.commit()
        cur.close()
        return redirect(url_for('index'))


    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT arborescence, libelle, delai, etat, type
        FROM structure_gdr
        WHERE niveau = 0 AND paire = 0 AND etat = 1 AND (type = 'M' OR type = 'P')
        ORDER BY CASE WHEN type = 'P' THEN 0 ELSE 1 END, arborescence
    """)
    raw_roots = cur.fetchall()

    objets = []
    for row in raw_roots:
        arbo = row[0]
        libelle = row[1]
        delai = row[2] or 0
        etat_par_defaut = row[3] or ''
        type_ = row[4]


        if type_ == 'P':
            objets.append({
                'code': arbo,
                'label': libelle,
                'sous_objets': []
            })
        else:

            cur.execute("""
                SELECT arborescence, libelle
                FROM structure_gdr
                WHERE arborescence LIKE %s AND paire != 0
            """, (arbo + '%',))
            sous_raw = cur.fetchall()
            sous_objets = [{'code': s[0], 'label': s[1]} for s in sous_raw]

            objets.append({
                'code': arbo,
                'label': libelle,
                'sous_objets': sous_objets
            })


    cur.execute("SELECT DISTINCT canal FROM reclamations")
    canaux = [row[0] for row in cur.fetchall()]

    cur.execute("SELECT DISTINCT etat_demande FROM reclamations")
    etat_demande = [row[0] for row in cur.fetchall()]

    cur.close()

    current_datetime = datetime.now().strftime('%Y-%m-%dT%H:%M')

    return render_template(
        'ajouter.html',
        objets=objets,
        canaux=canaux,
        etat_demande=etat_demande,
        current_datetime=current_datetime
    )


@app.route('/modifier_reclamation/<int:id>', methods=['GET', 'POST'])
def modifier_reclamation(id):
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        objet = request.form['objet']
        entite = request.form.get('entite', '')
        login = request.form['login']
        canal = request.form['canal']
        etat = request.form['etat']
        numero = request.form['numero']
        cause_reclamation = request.form.get('cause_reclamation', '')
        contact = request.form.get('contact', '')
        date_saisie = request.form['date_saisie']
        date_prevue_vid = request.form.get('date_prevue_vid') or None
        rem_saisie = request.form.get('rem_saisie', '')
        date_ext = request.form.get('date_ext') or None
        date_clo = request.form.get('date_clo') or None
        rem_clo = request.form.get('rem_clo', '')
        user_id = request.form.get('user_id', None)

        cur.execute("""
            UPDATE reclamations
            SET objet = %s, entite = %s, login = %s, canal = %s, etat_demande = %s,
                numero = %s, cause_reclamation = %s, contact = %s,
                date_saisie = %s, date_prevue_vid = %s, rem_saisie = %s,
                date_ext = %s, date_clo = %s, rem_clo = %s, user_id = %s
            WHERE id = %s
        """, (
            objet, entite, login, canal, etat,
            numero, cause_reclamation, contact,
            date_saisie, date_prevue_vid, rem_saisie,
            date_ext, date_clo, rem_clo, user_id,
            id
        ))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('index'))


    cur.execute("SELECT * FROM reclamations WHERE id = %s", (id,))
    reclamation = cur.fetchone()

    if not reclamation:
        cur.close()
        return "Réclamation non trouvée", 404


    cur.execute("""
        SELECT DISTINCT libelle
        FROM structure_gdr
        WHERE LEFT(arborescence, 2) IN ('1X', '2X', '3X', '4X') LIMIT 4;
    """)
    objets = [row[0] for row in cur.fetchall()]

    cur.execute("SELECT DISTINCT etat_demande FROM reclamations")
    etats = [row[0] for row in cur.fetchall()]

    cur.execute("SELECT DISTINCT canal FROM reclamations")
    canaux = [row[0] for row in cur.fetchall()]

    cur.close()

    return render_template(
        'modifier_reclamation.html',
        reclamation=reclamation,
        objets=objets,
        canaux=canaux,
        etats=etats
    )


@app.route('/supprimer_reclamation/<int:id>')
def supprimer_reclamation(id):
    if 'userlogin' not in session:
        return redirect(url_for('se_connecter'))
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM reclamations WHERE id = %s", (id,))
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

    datasets_48h_etat = [{
        "label": f"État : {etat}",
        "data": [valeurs.get(h, 0) for h in heures],
        "borderColor": "rgba(54, 162, 235, 0.8)",
        "backgroundColor": "rgba(54, 162, 235, 0.1)",
        "fill": True,
        "tension": 0.4
    } for etat, valeurs in data_par_etat.items()]

    datasets_48h_canal = [{
        "label": f"Canal : {canal}",
        "data": [valeurs.get(h, 0) for h in heures],
        "borderColor": "rgba(255, 99, 132, 0.8)",
        "backgroundColor": "rgba(255, 99, 132, 0.1)",
        "fill": True,
        "tension": 0.4
    } for canal, valeurs in data_par_canal.items()]

    # Réclamations pour utilisateur (login) sur 48h
    cur.execute("""
        SELECT DATE_FORMAT(date_saisie, '%Y-%m-%d %H:00:00') AS heure, login, COUNT(*) as total
        FROM reclamations
        WHERE date_saisie >= NOW() - INTERVAL 48 HOUR
        GROUP BY heure, login
        ORDER BY heure
    """)
    grouped_48h_login = cur.fetchall()

    data_par_login = defaultdict(lambda: defaultdict(int))
    for heure, login, total in grouped_48h_login:
        data_par_login[login][heure] += total

    datasets_48h_login = [{
        "label": f"Utilisateur : {login}",
        "data": [valeurs.get(h, 0) for h in heures],
        "borderColor": f"rgba({hash(login) % 255}, {(hash(login) // 255) % 255}, {(hash(login) // 65025) % 255}, 0.8)",
        "backgroundColor": f"rgba({hash(login) % 255}, {(hash(login) // 255) % 255}, {(hash(login) // 65025) % 255}, 0.1)",
        "fill": True,
        "tension": 0.4
    } for login, valeurs in data_par_login.items()]

    # Données par mois et état
    cur.execute("""
        SELECT mois, etat_demande, total
        FROM etat_par_mois
        ORDER BY mois
    """)
    etat_par_mois = cur.fetchall()

    mois_uniques = sorted(set(row[0] for row in etat_par_mois))
    etats = sorted(set(row[1] for row in etat_par_mois))
    mois_index = {mois: i for i, mois in enumerate(mois_uniques)}
    totaux_par_mois = defaultdict(int)
    valeurs_etat_par_mois = {etat: [0] * len(mois_uniques) for etat in etats}

    for mois, etat, total in etat_par_mois:
        index = mois_index[mois]
        totaux_par_mois[mois] += total
        valeurs_etat_par_mois[etat][index] += total

    datasets_etat_par_mois = [{
        "label": etat,
        "data": [
            round((val / totaux_par_mois[mois]) * 100, 2) if totaux_par_mois[mois] else 0
            for mois, val in zip(mois_uniques, valeurs)
        ],
        "backgroundColor": f"rgba({hash(etat) % 255}, {(hash(etat) // 255) % 255}, {(hash(etat) // 65025) % 255}, 0.6)"
    } for etat, valeurs in valeurs_etat_par_mois.items()]

    cur.execute("""
        SELECT mois, categorie, etat_demande, total
        FROM etat_cat_par_mois
        ORDER BY mois
    """)
    etat_cat_par_mois = cur.fetchall()

    mois_uniques = sorted(set(row[0] for row in etat_cat_par_mois))
    categories = sorted(set(row[1] for row in etat_cat_par_mois))
    etats = sorted(set(row[2] for row in etat_cat_par_mois))
    mois_index = {mois: i for i, mois in enumerate(mois_uniques)}

    data_par_categorie = {}
    for cat in categories:
        filtred = [row for row in etat_cat_par_mois if row[1] == cat]
        totaux_par_mois = defaultdict(int)
        valeurs_etat_par_mois = {etat: [0] * len(mois_uniques) for etat in etats}

        for mois, _, etat, total in filtred:
            index = mois_index[mois]
            totaux_par_mois[mois] += total
            valeurs_etat_par_mois[etat][index] += total

        datasets = [{
            "label": etat,
            "data": [
                round((val / totaux_par_mois[mois]) * 100, 2) if totaux_par_mois[mois] else 0
                for mois, val in zip(mois_uniques, valeurs)
            ],
            "backgroundColor": f"rgba({hash(etat + cat) % 255}, {(hash(etat + cat) // 255) % 255}, {(hash(etat + cat) // 65025) % 255}, 0.6)"
        } for etat, valeurs in valeurs_etat_par_mois.items()]

        data_par_categorie[cat] = {
            "labels": mois_uniques,
            "datasets": datasets
        }

    data_par_categorie_par_mois = {}
    for cat in categories:
        filtred = [row for row in etat_cat_par_mois if row[1] == cat]
        data_par_categorie_par_mois[cat] = {}
        for mois in mois_uniques:
            filtred_mois = [row for row in filtred if row[0] == mois]
            total_mois = sum(row[3] for row in filtred_mois)
            datasets = [{
                "label": etat,
                "data": [round((sum(row[3] for row in filtred_mois if row[2] == etat) / total_mois) * 100, 2) if total_mois else 0],
                "backgroundColor": f"rgba({hash(etat + cat) % 255}, {(hash(etat + cat) // 255) % 255}, {(hash(etat + cat) // 65025) % 255}, 0.6)"
            } for etat in etats]

            data_par_categorie_par_mois[cat][mois] = {
                "labels": [mois],
                "datasets": datasets
            }

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
        labels_48h_login=heures,
        datasets_48h_login=datasets_48h_login,
        labels_mois_etat=mois_uniques,
        datasets_mois_etat=datasets_etat_par_mois,
        data_par_categorie=data_par_categorie,
        data_par_categorie_par_mois=json.dumps(data_par_categorie_par_mois)
    )
@app.route('/update_stats_mensuelles')
def update_stats_mensuelles():
    cur = mysql.connection.cursor()

    # 1. Créer des tables temporaires
    cur.execute("""
        CREATE TEMPORARY TABLE temp_etat_par_mois AS
        SELECT DATE_FORMAT(date_saisie, '%Y-%m') AS mois, etat_demande, COUNT(*) AS total
        FROM reclamations
        WHERE date_saisie >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
        GROUP BY mois, etat_demande
    """)

    cur.execute("""
        CREATE TEMPORARY TABLE temp_etat_cat_par_mois AS
        SELECT DATE_FORMAT(r.date_saisie, '%Y-%m') AS mois,
               LEFT(s.arborescence, 2) AS categorie,
               r.etat_demande,
               COUNT(*) AS total
        FROM reclamations r
        JOIN structure_gdr s ON r.objet = s.libelle
        WHERE r.date_saisie >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
          AND LEFT(s.arborescence, 2) IN ('1X', '2X', '3X', '4X')
        GROUP BY mois, categorie, r.etat_demande
    """)

    # 2. Vider les tables réelles
    cur.execute("DELETE FROM etat_par_mois")
    cur.execute("DELETE FROM etat_cat_par_mois")

    # 3. Insérer les données depuis les tables temporaires
    cur.execute("INSERT INTO etat_par_mois SELECT * FROM temp_etat_par_mois")
    cur.execute("INSERT INTO etat_cat_par_mois SELECT * FROM temp_etat_cat_par_mois")

    mysql.connection.commit()
    cur.close()
    return redirect(url_for('analyse_temporelle'))




@app.route('/structure_gdr')
def structure_gdr():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM structure_gdr")


    column_names = [desc[0] for desc in cur.description]


    results = [dict(zip(column_names, row)) for row in cur.fetchall()]

    cur.close()
    return render_template('structure_gdr.html', structure_gdr=results)



@app.route('/reclamations')
def reclamations():
    q = request.args.get('q', '').strip()
    return render_template('reclamations.html', q=q)

# API لجلب النتائج بشكل JSON حسب الصفحة والبحث
@app.route('/api/reclamations')
def api_reclamations():
    page = int(request.args.get('page', 1))
    q = request.args.get('q', '').strip()
    per_page = 10
    offset = (page - 1) * per_page

    cur = mysql.connection.cursor(DictCursor)

    params = []
    base_query = "SELECT numero, objet, entite, canal, etat_demande, cause_reclamation, date_saisie FROM reclamations_cached WHERE date_saisie != '0000-00-00 00:00:00' "
    count_query = "SELECT COUNT(*) as count FROM reclamations_cached WHERE date_saisie != '0000-00-00 00:00:00' "

    if q:
        base_query += "AND MATCH(numero, objet, entite, canal, cause_reclamation) AGAINST (%s IN BOOLEAN MODE) "
        count_query += "AND MATCH(numero, objet, entite, canal, cause_reclamation) AGAINST (%s IN BOOLEAN MODE) "
        params.append(q + '*')

    base_query += "ORDER BY date_saisie DESC LIMIT %s OFFSET %s"
    params.extend([per_page, offset])

    cur.execute(base_query, params)
    reclamations = cur.fetchall()

    cur.execute(count_query, params[:-2] if q else [])
    total_count = cur.fetchone()['count']

    cur.close()

    return jsonify({
        "reclamations": reclamations,
        "page": page,
        "per_page": per_page,
        "total_count": total_count
    })

@app.route('/update_cache')
def update_cache():
    try:
        cur_write = mysql.connection.cursor()
        cur_read = mysql.connection.cursor()

        # Vider le cache
        cur_write.execute("DELETE FROM reclamations_cached")
        mysql.connection.commit()

        # Lecture par batches avec fetchmany()
        select_query = """
            SELECT objet, entite, login, canal, etat_demande, numero,
                   cause_reclamation, contact, date_saisie, date_prevue_vid,
                   rem_saisie, date_ext, date_clo, rem_clo, user_id
            FROM reclamations
        """
        cur_read.execute(select_query)

        insert_query = """
            INSERT INTO reclamations_cached (
                objet, entite, login, canal, etat_demande, numero,
                cause_reclamation, contact, date_saisie, date_prevue_vid,
                rem_saisie, date_ext, date_clo, rem_clo, user_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        batch_size = 10000
        while True:
            rows = cur_read.fetchmany(batch_size)
            if not rows:
                break
            cur_write.executemany(insert_query, rows)
            mysql.connection.commit()

        message = "Les données ont été mises à jour avec succès."
    except Exception as e:
        mysql.connection.rollback()
        message = f"Une erreur est survenue lors de la mise à jour : {str(e)}"
    finally:
        cur_read.close()
        cur_write.close()

    return redirect(url_for('reclamations', message=message))


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
