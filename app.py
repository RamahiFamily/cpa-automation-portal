python app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from engine import CPAAutomationEngine

app = Flask(__name__)
CORS(app) # Enables connection from your frontend HTML page
engine = CPAAutomationEngine()

@app.route('/api/upload-shoebox', methods=['POST'])
def upload_shoebox():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    file = request.files['file']
    temp_path = f"/tmp/{file.filename}"
    file.save(temp_path)

    try:
        # Runs real Gemini 3.8 Flash extraction & stages into Supabase
        result = engine.process_shoebox_document(temp_path)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000)
