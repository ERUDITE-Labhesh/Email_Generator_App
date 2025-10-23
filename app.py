from flask import Flask, render_template, request, jsonify
from langchain_email_generator import run_email_generation_pipeline
import threading
import uuid

app = Flask(__name__)

TASKS = {}

@app.route('/')
def home():
    return render_template('index.html')

@app.route("/start-email-generation", methods=['POST'])
def start_email_generation():
    data = request.json
    analysis_id = data.get("analysis_id")

    if not analysis_id:
        return jsonify({"error": "analysis_id is required"}), 400

    task_id = str(uuid.uuid4())
    TASKS[task_id] = {"status": "Finding the Inital Analysis...", "result": None}

    def background_job(task_id, analysis_id):
        try:
            TASKS[task_id]["status"] = "Gap analysis running..."
            result = run_email_generation_pipeline(analysis_id)
            TASKS[task_id]["status"] = "Completed"
            TASKS[task_id]["result"] = result
        except Exception as e:
            TASKS[task_id]["status"] = f"Error: {str(e)}"

    thread = threading.Thread(target=background_job, args=(task_id, analysis_id))
    thread.start()

    return jsonify({"task_id": task_id})

@app.route("/task-status/<task_id>", methods=["GET"])
def task_status(task_id):
    task = TASKS.get(task_id)
    if not task:
        return jsonify({"error": "Invalid task ID"}), 404
    return jsonify(task)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
