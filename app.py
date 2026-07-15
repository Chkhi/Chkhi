from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=os.environ.get('DB_PORT', '5432'),
        database=os.environ.get('DB_NAME', 'my_clinic'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', ''),
        sslmode=os.environ.get('PGSSLMODE', 'require')
    )

@app.route('/')
def home():
    return jsonify({'message': 'API работает! Используйте /api/patient/1 для получения данных'})

@app.route('/api/patient/<int:patient_id>')
def get_patient(patient_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Данные пациента
        cur.execute("""
            SELECT patient_id, first_name, last_name, patronymic, 
                   birth_date, phone, email
            FROM patients 
            WHERE patient_id = %s
        """, (patient_id,))
        patient = cur.fetchone()
        
        if not patient:
            return jsonify({'error': 'Пациент не найден'}), 404
        
        # Зубная карта
        cur.execute("""
            SELECT tooth_number, status, notes
            FROM teeth_status
            WHERE patient_id = %s
            ORDER BY tooth_number
        """, (patient_id,))
        teeth = cur.fetchall()
        
        # История посещений
        cur.execute("""
            SELECT v.visit_date, v.diagnosis, v.treatment, v.cost,
                   d.first_name, d.last_name, d.specialization
            FROM visits v
            JOIN doctors d ON v.doctor_id = d.doctor_id
            WHERE v.patient_id = %s
            ORDER BY v.visit_date DESC
        """, (patient_id,))
        visits = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'patient': {
                'id': patient[0],
                'firstName': patient[1],
                'lastName': patient[2],
                'patronymic': patient[3] or '',
                'birthDate': patient[4].strftime('%d.%m.%Y') if patient[4] else None,
                'phone': patient[5] or '',
                'email': patient[6]
            },
            'teeth': [
                {'number': t[0], 'status': t[1], 'notes': t[2] or ''}
                for t in teeth
            ],
            'visits': [
                {
                    'date': v[0].strftime('%d.%m.%Y %H:%M') if v[0] else None,
                    'diagnosis': v[1] or '',
                    'treatment': v[2] or '',
                    'cost': float(v[3]) if v[3] else 0,
                    'doctor': f"{v[4]} {v[5]}" if v[4] else '',
                    'specialization': v[6] or ''
                }
                for v in visits
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- НОВЫЙ ЭНДПОИНТ: ДОБАВЛЕНИЕ ПОСЕЩЕНИЯ ---
@app.route('/api/visit', methods=['POST'])
def add_visit():
    try:
        data = request.json
        patient_id = data.get('patient_id')
        doctor_id = data.get('doctor_id')
        diagnosis = data.get('diagnosis')
        treatment = data.get('treatment')
        cost = data.get('cost')
        visit_date = data.get('visit_date', datetime.now().isoformat())
        
        # Проверка, что все поля заполнены
        if not all([patient_id, doctor_id, diagnosis, treatment, cost]):
            return jsonify({'error': 'Все поля обязательны'}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO visits (patient_id, doctor_id, visit_date, diagnosis, treatment, cost, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'завершён')
            RETURNING visit_id
        """, (patient_id, doctor_id, visit_date, diagnosis, treatment, cost))
        
        visit_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'visit_id': visit_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
