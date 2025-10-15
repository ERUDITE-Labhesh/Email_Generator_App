from flask import Flask, render_template, request, jsonify
from langchain_email_generator import run_email_generation_pipeline

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')


@app.route("/generate-email", methods=['POST'])
def generate_email():
    data = request.json
    analysis_id = data.get("analysis_id")

    if not analysis_id:
        return jsonify({"error": "analysis_id is required"}), 400
    
    try:
        result = run_email_generation_pipeline(analysis_id)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    # app.run(debug=True)
    app.run(host='0.0.0.0', port=5000)