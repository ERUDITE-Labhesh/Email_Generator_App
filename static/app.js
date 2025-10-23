document.addEventListener("DOMContentLoaded", function() {
  const generateBtn = document.getElementById("generate-btn");
  const inputSection = document.getElementById("input-section");
  const emailsSection = document.getElementById("emails-section");
  const loader = document.getElementById("loader");
  const statusText = document.getElementById("status-text"); // 👈 reference to loader text

  generateBtn.addEventListener("click", async () => {
    const analysisId = document.getElementById("analysis-id").value.trim();
    if (!analysisId) {
      alert("Please enter an analysis ID");
      return;
    }

    generateBtn.disabled = true;
    generateBtn.textContent = "Generating...";
    loader.classList.remove("hidden");
    statusText.textContent = "Starting...";

    try {
      // 1️⃣ Start background task
      const startResponse = await fetch("/start-email-generation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ analysis_id: analysisId })
      });

      if (!startResponse.ok) throw new Error("Failed to start task");
      const { task_id } = await startResponse.json();

      // 2️⃣ Poll every 2 seconds for task status
      const pollInterval = setInterval(async () => {
        const statusResponse = await fetch(`/task-status/${task_id}`);
        if (!statusResponse.ok) return;

        const statusData = await statusResponse.json();
        console.log("Status:", statusData.status);

        // Update loader message dynamically
        statusText.textContent = statusData.status;

        if (statusData.status === "Completed" && statusData.result) {
          clearInterval(pollInterval);

          // Render results
          const data = statusData.result;
          inputSection.classList.add("hidden");
          emailsSection.innerHTML = "";
          emailsSection.classList.remove("hidden");

          data.emails.forEach(email => {
            const emailBox = document.createElement("div");
            emailBox.className = "bg-gray-100 p-4 rounded-2xl shadow-neumorphism relative mb-4";

            const copyBtn = document.createElement("button");
            copyBtn.textContent = "📋";
            copyBtn.className = "absolute top-3 right-3 text-lg copy-btn";
            copyBtn.addEventListener("click", () => {
              navigator.clipboard.writeText(email.email_body);
              alert("Copied to clipboard!");
            });
            emailBox.appendChild(copyBtn);

            const subject = document.createElement("h2");
            subject.className = "text-lg font-bold mb-2";
            subject.textContent = email.subject_line;
            emailBox.appendChild(subject);

            const body = document.createElement("p");
            body.className = "text-gray-700 whitespace-pre-line";
            body.textContent = email.email_body;
            emailBox.appendChild(body);

            emailsSection.appendChild(emailBox);
          });

          // Add "Start New Analysis" button
          const newAnalysisBtn = document.createElement("button");
          newAnalysisBtn.textContent = "Start New Analysis";
          newAnalysisBtn.className = "mt-4 bg-gray-400 text-white py-2 px-4 rounded-lg hover:bg-gray-500";
          newAnalysisBtn.addEventListener("click", () => {
            emailsSection.classList.add("hidden");
            emailsSection.innerHTML = "";
            inputSection.classList.remove("hidden");
            document.getElementById("analysis-id").value = "";
          });
          emailsSection.appendChild(newAnalysisBtn);

          loader.classList.add("hidden");
          generateBtn.disabled = false;
          generateBtn.textContent = "Generate";
        }
      }, 2000);

    } catch (err) {
      alert("Error generating emails. Check console.");
      console.error(err);
      generateBtn.disabled = false;
      generateBtn.textContent = "Generate";
      loader.classList.add("hidden");
    }
  });
});
