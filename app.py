import os
from flask import Flask, render_template, request, jsonify
from google.cloud import firestore
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Configuración de Firestore
PROJECT_ID = "surfn-peru"
DATABASE_ID = "expenses"
# Joey

# Inicializar cliente de Firestore
db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)
collection_name = "expenses"
users_collection = "users"
categories_collection = "categories"
clients_collection = "clients"

def initialize_categories():
    """Inicializa la colección de categorías si está vacía."""
    try:
        docs = db.collection(categories_collection).limit(1).stream()
        if not any(docs):
            print("Inicializando categorías en Firestore...")
            initial_categories = [
                "Auto-Gasolina", "Auto-Estacionamiento", "Auto-Otros",
                "Gasto-Rep-Comida", "Gasto-Rep-Otros", "Servicios-Misc", "Viajes-Misc"
            ]
            batch = db.batch()
            for cat in initial_categories:
                doc_ref = db.collection(categories_collection).document(cat)
                batch.set(doc_ref, {"name": cat})
            batch.commit()
            print("Categorías inicializadas.")
    except Exception as e:
        print(f"Error inicializando categorías: {e}")

def initialize_clients():
    """Inicializa la colección de clientes si está vacía."""
    try:
        docs = db.collection(clients_collection).limit(1).stream()
        if not any(docs):
            print("Inicializando clientes en Firestore...")
            initial_clients = [
                "Delosi", "Cliente-1", "Cliente-2", "Cliente-3", "Cliente-4",
                "Cliente-5", "Cliente-6", "Cliente-7", "Cliente-8", "Cliente-9",
                "Cliente-10", "Cliente-11", "Cliente-12", "Cliente-13", "Cliente-14", "Cliente-15"
            ]
            batch = db.batch()
            for client in initial_clients:
                doc_ref = db.collection(clients_collection).document(client)
                batch.set(doc_ref, {"company_name": client})
            batch.commit()
            print("Clientes inicializados.")
    except Exception as e:
        print(f"Error inicializando clientes: {e}")

# Initialize categories on startup
# Initialize categories on startup
initialize_categories()
initialize_clients()

def initialize_admin_user():
    """Crea un usuario administrador por defecto si no existe."""
    try:
        admin_ref = db.collection(users_collection).document("admin")
        if not admin_ref.get().exists:
            print("Creando usuario admin por defecto...")
            hashed_password = generate_password_hash("admin123")
            admin_data = {
                "username": "admin",
                "password": hashed_password,
                "role": "admin",
                "created_at": firestore.SERVER_TIMESTAMP
            }
            admin_ref.set(admin_data)
            print("Usuario admin creado.")
    except Exception as e:
        print(f"Error inicializando admin: {e}")

initialize_admin_user()

def is_admin(user_id):
    """Determina si un usuario es administrador."""
    # TODO: In the future, check role in DB
    return user_id and (user_id.startswith("Gerente-") or user_id == "admin")

@app.route('/admin')
def admin_dashboard():
    return render_template('admin.html')

@app.route('/')
def index():
    return render_template('recibos.html')

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"status": "error", "message": "Faltan datos"}), 400

        # Check if user exists
        user_ref = db.collection(users_collection).document(username)
        if user_ref.get().exists:
            return jsonify({"status": "error", "message": "El usuario ya existe"}), 409

        # Create user
        hashed_password = generate_password_hash(password)
        user_data = {
            "username": username,
            "password": hashed_password,
            "role": "user", # Default role
            "created_at": firestore.SERVER_TIMESTAMP
        }
        user_ref.set(user_data)
        
        return jsonify({"status": "success", "username": username}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"status": "error", "message": "Faltan datos"}), 400

        user_ref = db.collection(users_collection).document(username)
        doc = user_ref.get()

        if not doc.exists:
             return jsonify({"status": "error", "message": "Usuario no encontrado"}), 404
        
        user_data = doc.to_dict()
        if check_password_hash(user_data.get('password'), password):
            return jsonify({"status": "success", "username": username, "role": user_data.get('role', 'user')}), 200
        else:
            return jsonify({"status": "error", "message": "Contraseña incorrecta"}), 401

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        users = db.collection(users_collection).stream()
        user_list = [doc.id for doc in users]
        return jsonify(user_list), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        db.collection(users_collection).document(user_id).delete()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        data = request.json
        password = data.get('password')
        if not password:
            return jsonify({"status": "error", "message": "Password required"}), 400
            
        hashed_password = generate_password_hash(password)
        db.collection(users_collection).document(user_id).update({"password": hashed_password})
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/categories', methods=['GET'])
def get_categories():
    try:
        categories = db.collection(categories_collection).stream()
        category_list = [doc.to_dict().get('name') for doc in categories]
        # Filter out None values just in case
        category_list = [c for c in category_list if c]
        return jsonify(sorted(category_list)), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/categories', methods=['POST'])
def add_category():
    try:
        data = request.json
        name = data.get('name')
        if not name:
            return jsonify({"status": "error", "message": "Nombre requerido"}), 400
        
        db.collection(categories_collection).document(name).set({"name": name})
        return jsonify({"status": "success"}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/categories/<category_id>', methods=['DELETE'])
def delete_category(category_id):
    try:
        db.collection(categories_collection).document(category_id).delete()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/categories/<category_id>', methods=['PUT'])
def update_category(category_id):
    try:
        data = request.json
        name = data.get('name')
        if not name:
            return jsonify({"status": "error", "message": "Name required"}), 400
            
        db.collection(categories_collection).document(category_id).update({"name": name})
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/clients', methods=['GET'])
def get_clients():
    try:
        clients = db.collection(clients_collection).stream()
        # Support both 'name' (legacy/default) and 'company_name' (imported data)
        client_list = []
        for doc in clients:
            data = doc.to_dict()
            name = data.get('company_name') or data.get('name')
            if name:
                client_list.append(name)
        return jsonify(sorted(client_list)), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/clients', methods=['POST'])
def add_client():
    try:
        data = request.json
        name = data.get('name') # Frontend should send 'name'
        if not name:
            return jsonify({"status": "error", "message": "Nombre requerido"}), 400
        
        # Use name as doc ID for simplicity, matching initialize_clients
        db.collection(clients_collection).document(name).set({"company_name": name})
        return jsonify({"status": "success"}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/clients/<client_id>', methods=['DELETE'])
def delete_client(client_id):
    try:
        db.collection(clients_collection).document(client_id).delete()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/clients/<client_id>', methods=['PUT'])
def update_client(client_id):
    try:
        data = request.json
        company_name = data.get('company_name')
        if not company_name:
            return jsonify({"status": "error", "message": "Company Name required"}), 400
            
        db.collection(clients_collection).document(client_id).update({"company_name": company_name})
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

from bq_import import sync_firestore_to_bigquery

@app.route('/api/bq-export', methods=['POST'])
def bq_export():
    try:
        sync_firestore_to_bigquery()
        return jsonify({"status": "success", "message": "Exportación a BigQuery completada correctament."}), 200
    except Exception as e:
         return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/expenses', methods=['POST'])
def add_expense():
    try:
        data = request.json
        update_time, doc_ref = db.collection(collection_name).add(data)
        return jsonify({"status": "success", "id": doc_ref.id}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    try:
        user_id = request.args.get('user_id')
        search_query = request.args.get('search', '').lower()
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        category = request.args.get('category')
        client = request.args.get('client')

        query = db.collection(collection_name)

        # 1. Filtro de Seguridad (Role-based)
        if not is_admin(user_id):
            query = query.where("ejecutivo", "==", user_id)

        # 2. Filtros Específicos
        if category:
            query = query.where("categoria", "==", category)
        if client:
            query = query.where("cliente", "==", client)
        if date_from:
            query = query.where("fecha", ">=", date_from)
        if date_to:
            query = query.where("fecha", "<=", date_to)

        # Ordenar por fecha descending
        # NOTA: Si se usan múltiples filtros de desigualdad, Firestore requiere un índice compuesto.
        query = query.order_by('fecha', direction=firestore.Query.DESCENDING)
        
        docs = query.limit(100).stream()
        
        results = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            
            # Filtro de búsqueda textual (establecimiento) en memoria para evitar complejidad de índices
            if search_query:
                content = f"{item.get('establecimiento', '')} {item.get('descripcion', '')}".lower()
                if search_query in content:
                    results.append(item)
            else:
                results.append(item)
                
        return jsonify(results)
    except Exception as e:
        print(f"ERROR en get_expenses: {e}")
        # Si Firestore arroja un error de índice faltante, el mensaje contendrá el link para crearlo.
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/expenses/<doc_id>', methods=['DELETE'])
def delete_expense(doc_id):
    try:
        db.collection(collection_name).document(doc_id).delete()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)


