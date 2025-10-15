document.addEventListener("DOMContentLoaded", function() {
  const generateBtn = document.getElementById("generate-btn");
  const inputSection = document.getElementById("input-section");
  const emailsSection = document.getElementById("emails-section");
  const loader = document.getElementById("loader");

  generateBtn.addEventListener("click", async () => {
    const analysisId = document.getElementById("analysis-id").value.trim();
    if (!analysisId) {
      alert("Please enter an analysis ID");
      return;
    }

    // Disable button and show loader
    generateBtn.disabled = true;
    generateBtn.textContent = "Generating...";
    loader.classList.remove("hidden");

    try {
      const response = await fetch("/generate-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ analysis_id: analysisId })
      });

      if (!response.ok) throw new Error("Failed to fetch");

      const data = await response.json();

      // Hide input section, show emails
      inputSection.classList.add("hidden");
      emailsSection.innerHTML = "";
      emailsSection.classList.remove("hidden");

      data.emails.forEach(email => {
        const emailBox = document.createElement("div");
        emailBox.className = "bg-gray-100 p-4 rounded-2xl shadow-neumorphism relative mb-4";

        // Copy button
        const copyBtn = document.createElement("button");
        copyBtn.textContent = "📋";
        copyBtn.className = "absolute top-3 right-3 text-lg copy-btn";
        copyBtn.addEventListener("click", () => {
          navigator.clipboard.writeText(email.email_body);
          alert("Copied to clipboard!");
        });
        emailBox.appendChild(copyBtn);

        // Subject
        const subject = document.createElement("h2");
        subject.className = "text-lg font-bold mb-2";
        subject.textContent = email.subject_line;
        emailBox.appendChild(subject);

        // Body (with paragraphs)
        const body = document.createElement("p");
        body.className = "text-gray-700 whitespace-pre-line";
        body.textContent = email.email_body;
        emailBox.appendChild(body);

        emailsSection.appendChild(emailBox);
      });

      // New Analysis button
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

    } catch (err) {
      alert("Error generating emails. Check console for details.");
      console.error(err);
    } finally {
      generateBtn.disabled = false;
      generateBtn.textContent = "Generate";
      loader.classList.add("hidden");
    }
  });
});
