let regenCount = 0; // track regeneration attempts
const MAX_REGEN = 3;

document.addEventListener("DOMContentLoaded", function () {
  const generateBtn = document.getElementById("generate-btn");
  const inputSection = document.getElementById("input-section");
  const emailsSection = document.getElementById("emails-section");

  const loader = document.getElementById("loader");
  const statusText = document.getElementById("status-text"); 

  // ---------- GENERATE EMAILS ----------
  generateBtn.addEventListener("click", async () => {
    const analysisId = document.getElementById("analysis-id").value.trim();
    const designation = document.getElementById("designation").value.trim();
    const linkedinUrl = document.getElementById("linkedin-url").value.trim();
    
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
        body: JSON.stringify({ 
          analysis_id: analysisId,
          designation: designation,
          linkedin_url: linkedinUrl
        }),
      });

      if (!startResponse.ok) throw new Error("Failed to start task");
      const { task_id } = await startResponse.json();

      // Poll task status
      pollTaskStatus(task_id, analysisId, false, designation, linkedinUrl);
    } catch (err) {
      console.error(err);
      alert("Error generating emails. Check console.");
      loader.classList.add("hidden");
      generateBtn.disabled = false;
      generateBtn.textContent = "Generate";
      statusText.textContent = ""; 
    }
  });

  // ---------- POLLING FUNCTION ----------
  async function pollTaskStatus(taskId, analysisId, isRegeneration = false, designation = "", linkedinUrl = "") {
    const pollInterval = setInterval(async () => {
      try {
        const statusResponse = await fetch(`/task-status/${taskId}`);
        if (!statusResponse.ok) {
             console.error(`Polling error for task ${taskId}: ${statusResponse.status}`);
             return; 
        }

        const statusData = await statusResponse.json();
        console.log("Status:", statusData.status);
 
          if (statusData.status === "ERROR: ACCOUNT_EXHAUSTED") {
          clearInterval(pollInterval);
          loader.classList.add("hidden");

          alert("Contact Admin - Account Exhausted");
          setTimeout(() => {
            statusText.textContent = "";
            if (isRegeneration) {
              const regenerateBtn = document.querySelector("#emails-section button:last-child");
              if (regenerateBtn) {
                regenerateBtn.disabled = false;
                regenerateBtn.textContent = "Regenerate Email";
              }
            } else {
              generateBtn.disabled = false;
              generateBtn.textContent = "Generate";
            }
          }, 4000);

          return;
        }

        // Update loader message
        statusText.textContent = statusData.status;

        if (statusData.status === "Completed" && statusData.result) {
          clearInterval(pollInterval);
          loader.classList.add("hidden");
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

          renderEmails(statusData.result, analysisId, isRegeneration, designation, linkedinUrl);
        }else if (statusData.status.startsWith("Error:")) { // General error handling
                clearInterval(pollInterval);
                loader.classList.add("hidden");
                statusText.textContent = "An error occurred. See console.";
                currentBtn.disabled = false;
                currentBtn.textContent = isRegeneration ? "Regenerate Email" : "Generate";
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
  function renderEmails(data, analysisId, isRegeneration, designation, linkedinUrl = "") {
    if (!isRegeneration) inputSection.classList.add("hidden");
    emailsSection.classList.remove("hidden");
    emailsSection.innerHTML = "";

    const emails = Array.isArray(data.emails) ? data.emails : [];
    data.emails.forEach((email) => {
      const emailBox = document.createElement("div");
      emailBox.className = "bg-gray-100 p-4 rounded-2xl shadow-neumorphism mb-4 flex flex-col gap-2 h-full";
      const subject = document.createElement("h2");
      subject.className = "text-lg font-bold mb-2";
      subject.textContent = email.subject_line;
      emailBox.appendChild(subject);

      const body = document.createElement("p");
      body.className = "text-gray-700 whitespace-pre-line flex-1";
      body.textContent = email.email_body;
      emailBox.appendChild(body);

      // NEW: Add designation indicator if available at bottom-right
      if (designation) {
        const designationTag = document.createElement("div");
        const designationSpan=document.createElement("span")
        designationTag.className = "flex justify-end";
        emailBox.appendChild(designationTag);

        designationSpan.className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full"
        designationSpan.textContent = designation;

        designationTag.appendChild(designationSpan)

      }

      if (linkedinUrl) {
        const linkDiv = document.createElement("div");
        linkDiv.className = "text-xs text-gray-500 mt-2 break-all";
        linkDiv.textContent = `Personalized using: ${linkedinUrl}`;
        emailBox.appendChild(linkDiv);
  
    }
      emailsSection.appendChild(emailBox);
    });

    // "Start New Analysis" button
    const newAnalysisBtn = document.createElement("button");
    newAnalysisBtn.textContent = "Start New Analysis";
    newAnalysisBtn.className =
      "mt-4 bg-gray-400 text-white py-2 px-4 rounded-lg hover:bg-gray-500";
    newAnalysisBtn.addEventListener("click", () => {
      regenCount = 0; // reset counter for new analysis
      emailsSection.classList.add("hidden");
      emailsSection.innerHTML = "";
      inputSection.classList.remove("hidden");
      document.getElementById("analysis-id").value = "";
      document.getElementById("designation").value = "";
      document.getElementById("linkedin-url").value = "";

    });
    emailsSection.appendChild(newAnalysisBtn);

    // "Regenerate Email" button having "Regenerate Email" button with limit
  
    const regenerateBtn = document.createElement("button");
    regenerateBtn.textContent = `Regenerate Email (${regenCount}/${MAX_REGEN})`;
    regenerateBtn.className =
      "mt-4 bg-blue-500 text-white py-2 px-4 rounded-lg hover:bg-blue-600 ml-2";

    // Disable if already at max regenerations
    if (regenCount >= MAX_REGEN) {
      regenerateBtn.disabled = true;
      regenerateBtn.classList.add("opacity-50", "cursor-not-allowed");
      regenerateBtn.textContent = `Regenerate Email (${MAX_REGEN}/${MAX_REGEN})`;
    }

    regenerateBtn.addEventListener("click", async () => {
      if (regenCount < MAX_REGEN) {
        regenCount++;
        regenerateBtn.textContent = `Regenerate Email (${regenCount}/${MAX_REGEN})`;
        await regenerateEmail(analysisId, designation,linkedinUrl);

        // Disable button when limit is reached
        if (regenCount >= MAX_REGEN) {
          regenerateBtn.disabled = true;
          regenerateBtn.classList.add("opacity-50", "cursor-not-allowed");
          regenerateBtn.textContent = `Regenerate Email (${MAX_REGEN}/${MAX_REGEN})`;
        }
      }
    });

    emailsSection.appendChild(regenerateBtn);

  }

  // ---------- REGENERATE EMAIL FUNCTION ----------
  async function regenerateEmail(analysisId, designation, linkedinUrl = "") { 
    // Show the loader and set an initial status message
    loader.classList.remove("hidden"); 
    statusText.textContent = "Finalizing content..."; 

    try {
      const regenResponse = await fetch("/regenerate-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          analysis_id: analysisId, 
          designation: designation,
          linkedin_url: linkedinUrl
        }), // Send analysis_id and designation
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
      // Pass 'true' for isRegeneration flag and designation
      pollTaskStatus(task_id, analysisId, true, designation,linkedinUrl); 
    } catch (err) {
      console.error("Error during regeneration:", err);
      alert("Error regenerating email. Check console.");
      loader.classList.add("hidden"); // Hide loader on error
      statusText.textContent = ""; // Clear status on error
    }
  }
});