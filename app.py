import os
from flask import Flask, render_template, request, jsonify
from google.cloud import firestore

app = Flask(__name__)

# Configuración de Firestore
PROJECT_ID = "surfn-peru"
DATABASE_ID = "expenses"

# Inicializar cliente de Firestore
db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)
collection_name = "expenses"

def is_admin(user_id):
    """Determina si un usuario es administrador."""
    return user_id and user_id.startswith("Gerente-")

@app.route('/')
def index():
    return render_template('recibos.html')

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
