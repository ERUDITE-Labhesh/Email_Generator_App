from flask import Flask, render_template, request, jsonify
from langchain_email_generator import run_email_generation_pipeline
import threading
import uuid
import random
import os

app = Flask(__name__)

TASKS = {}
DEFAULT_MODEL = "x-ai/grok-4-fast"


@app.route('/')
def home():
    os.environ["OPENROUTER_MODEL"] = DEFAULT_MODEL
    print(f"Model reset to default: {DEFAULT_MODEL}")
    return render_template('index.html')

@app.route("/start-email-generation", methods=['POST'])
def start_email_generation():
    data = request.json
    analysis_id = data.get("analysis_id")

    if not analysis_id:
        return jsonify({"error": "analysis_id is required"}), 400
    
    os.environ["OPENROUTER_MODEL"] = DEFAULT_MODEL
    print(f"Starting new analysis with model: {DEFAULT_MODEL}")

    task_id = str(uuid.uuid4())
    TASKS[task_id] = {"status": "Finding the Inital Analysis...", "result": None}

    def background_job(task_id, analysis_id):
        try:
            TASKS[task_id]["status"] = "Gap analysis running..."
            result = run_email_generation_pipeline(analysis_id)
            TASKS[task_id]["status"] = "Completed"
            TASKS[task_id]["result"] = result
        except Exception as e:
            error_msg = str(e)
            if "INSUFFICIENT_CREDITS_ERROR" in error_msg or "402" in error_msg or "Insufficient credits" in error_msg:
                TASKS[task_id]["status"] = "ERROR: ACCOUNT_EXHAUSTED"
            else:
                TASKS[task_id]["status"] = f"Error: {str(e)}"


    thread = threading.Thread(target=background_job, args=(task_id, analysis_id))
    thread.start()

    return jsonify({"task_id": task_id})

@app.route("/regenerate-email", methods=["POST"])
def regenerate_email():
    data = request.json
    analysis_id = data.get("analysis_id")

    if not analysis_id:
        return jsonify({"error": "analysis_id is required"}), 400

    task_id = str(uuid.uuid4())
    TASKS[task_id] = {"status": "Regenerating email...", "result": None}

    # Randomly pick a model for regeneration
    model_list = [
        "google/gemini-2.5-flash",
        "qwen/qwen3-30b-a3b",
        "anthropic/claude-haiku-4.5"
    ]
    chosen_model = random.choice(model_list)
    print(f"Regenerating email using model: {chosen_model}")

    def background_regen_job(task_id, analysis_id, model_name):
        try:
            TASKS[task_id]["status"] = "Regenerating email..."
            result = run_email_generation_pipeline(analysis_id, custom_model=model_name)
            TASKS[task_id]["status"] = "Finalizing content..."
            TASKS[task_id]["result"] = result
            TASKS[task_id]["status"] = "Completed"
        except Exception as e:
            error_msg = str(e)
            if "INSUFFICIENT_CREDITS_ERROR" in error_msg or "402" in error_msg or "Insufficient credits" in error_msg:
                TASKS[task_id]["status"] = "ERROR: ACCOUNT_EXHAUSTED"
            else:
                TASKS[task_id]["status"] = f"Error: {str(e)}"

    thread = threading.Thread(target=background_regen_job, args=(task_id, analysis_id, chosen_model))
    thread.start()

    return jsonify({"task_id": task_id, "model_used": chosen_model})

@app.route("/task-status/<task_id>", methods=["GET"])
def task_status(task_id):
    task = TASKS.get(task_id)
    if not task:
        return jsonify({"error": "Invalid task ID"}), 404
    return jsonify(task)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
