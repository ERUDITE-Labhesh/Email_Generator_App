document.addEventListener("DOMContentLoaded", function () {
  const generateBtn = document.getElementById("generate-btn");
  const inputSection = document.getElementById("input-section");
  const emailsSection = document.getElementById("emails-section");
  // Make sure loader and statusText elements exist in your HTML
  const loader = document.getElementById("loader");
  const statusText = document.getElementById("status-text"); 

  // ---------- GENERATE EMAILS ----------
  generateBtn.addEventListener("click", async () => {
    const analysisId = document.getElementById("analysis-id").value.trim();
    if (!analysisId) {
      alert("Please enter an analysis ID");
      return;
    }

    generateBtn.disabled = true;
    generateBtn.textContent = "Generating...";
    loader.classList.remove("hidden"); // Show loader
    statusText.textContent = "Starting..."; // Set initial status

    try {
      const startResponse = await fetch("/start-email-generation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ analysis_id: analysisId }),
      });

      if (!startResponse.ok) throw new Error("Failed to start task");
      const { task_id } = await startResponse.json();

      // Poll task status
      pollTaskStatus(task_id, analysisId, false);
    } catch (err) {
      console.error(err);
      alert("Error generating emails. Check console.");
      loader.classList.add("hidden"); // Hide loader on error
      generateBtn.disabled = false;
      generateBtn.textContent = "Generate";
      statusText.textContent = ""; // Clear status on error
    }
  });

  // ---------- POLLING FUNCTION ----------
  async function pollTaskStatus(taskId, analysisId, isRegeneration = false) {
    const pollInterval = setInterval(async () => {
      try {
        const statusResponse = await fetch(`/task-status/${taskId}`);
        if (!statusResponse.ok) {
             // Consider stopping polling or handling specific errors
             console.error(`Polling error for task ${taskId}: ${statusResponse.status}`);
             return; // Skip this poll iteration
        }

        const statusData = await statusResponse.json();
        console.log("Status:", statusData.status);

        // New Feature - Check for Account Exchausted 
        if (statusData.status === "ERROR: ACCOUNT_EXHAUSTED") {
                clearInterval(pollInterval);
                loader.classList.add("hidden"); // Hide loader
                
                // Set the required user-facing message
                statusText.textContent = "Contact Admin - Account Exhausted"; 
                
                // Re-enable the relevant button(s) after 3 seconds for visibility
                setTimeout(() => {
                    statusText.textContent = "";
                    if (currentBtn) {
                        currentBtn.disabled = false;
                        currentBtn.textContent = isRegeneration ? "Regenerate Email" : "Generate";
                    }
                    if (!isRegeneration) {
                        generateBtn.disabled = false;
                        generateBtn.textContent = "Generate";
                    }
                }, 3000); 

                return; // Stop processing this poll
            }

        // Update loader message
        statusText.textContent = statusData.status;

        if (statusData.status === "Completed" && statusData.result) {
          clearInterval(pollInterval);
          loader.classList.add("hidden"); // Hide loader when complete
          // Enable generate button only if not regenerating
          if (!isRegeneration) {
              generateBtn.disabled = false;
              generateBtn.textContent = "Generate";
          }

          // Also ensure regenerate button is enabled if it exists - New Feature
                if (isRegeneration) {
                    const regenerateBtn = document.querySelector("#emails-section button:last-child");
                    if (regenerateBtn) {
                        regenerateBtn.disabled = false;
                        regenerateBtn.textContent = "Regenerate Email";
                    }
                }

          renderEmails(statusData.result, analysisId, isRegeneration);
        }else if (statusData.status.startsWith("Error:")) { // General error handling
                clearInterval(pollInterval);
                loader.classList.add("hidden");
                statusText.textContent = "An error occurred. See console.";
                if (currentBtn) {
                    currentBtn.disabled = false;
                    currentBtn.textContent = isRegeneration ? "Regenerate Email" : "Generate";
                }
        }
      } catch (err) {
          console.error("Error polling task status:", err);
          clearInterval(pollInterval);
          loader.classList.add("hidden"); // Hide loader on error
          if (!isRegeneration) {
              generateBtn.disabled = false;
              generateBtn.textContent = "Generate";
          }
          statusText.textContent = "Error polling status."; // Show error status
      }
    }, 2000); // Poll every 2 seconds
  }

  // ---------- RENDER EMAILS + BUTTONS ----------
  function renderEmails(data, analysisId, isRegeneration) {
    if (!isRegeneration) inputSection.classList.add("hidden");
    emailsSection.classList.remove("hidden");
    emailsSection.innerHTML = "";

    data.emails.forEach((email) => {
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

    // "Start New Analysis" button
    const newAnalysisBtn = document.createElement("button");
    newAnalysisBtn.textContent = "Start New Analysis";
    newAnalysisBtn.className =
      "mt-4 bg-gray-400 text-white py-2 px-4 rounded-lg hover:bg-gray-500";
    newAnalysisBtn.addEventListener("click", () => {
      emailsSection.classList.add("hidden");
      emailsSection.innerHTML = "";
      inputSection.classList.remove("hidden");
      document.getElementById("analysis-id").value = "";
    });
    emailsSection.appendChild(newAnalysisBtn);

    // "Regenerate Email" button
    const regenerateBtn = document.createElement("button");
    regenerateBtn.textContent = "Regenerate Email";
    regenerateBtn.className =
      "mt-4 bg-blue-500 text-white py-2 px-4 rounded-lg hover:bg-blue-600 ml-2";
    // Add event listener for regeneration
    regenerateBtn.addEventListener("click", async () => {
      await regenerateEmail(analysisId); // Pass analysisId
    });
    emailsSection.appendChild(regenerateBtn);
  }

  // ---------- REGENERATE EMAIL FUNCTION ----------
  async function regenerateEmail(analysisId) {
    // Show the loader and set an initial status message
    loader.classList.remove("hidden"); 
    statusText.textContent = "Finalizing content..."; 

    try {
      const regenResponse = await fetch("/regenerate-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ analysis_id: analysisId }), // Send analysis_id
      });

      if (!regenResponse.ok) {
          throw new Error(`Server responded with ${regenResponse.status}: ${regenResponse.statusText}`);
      }

      const { task_id, model_used } = await regenResponse.json();
      console.log("Regeneration started with model:", model_used);

      // Update status to reflect the chosen model
      // statusText.textContent = `Regenerating with ${model_used}...`;
      statusText.textContent = `Finalizing content... `;
      // Start polling for the regeneration task status
      // Pass 'true' for isRegeneration flag
      pollTaskStatus(task_id, analysisId, true); 
    } catch (err) {
      console.error("Error during regeneration:", err);
      alert("Error regenerating email. Check console.");
      loader.classList.add("hidden"); // Hide loader on error
      statusText.textContent = ""; // Clear status on error
    }
  }
});