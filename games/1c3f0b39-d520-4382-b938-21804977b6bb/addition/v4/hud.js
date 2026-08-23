(function () {
  const C = window.ORBIT;

  class Hud {
    constructor(tuning, callbacks) {
      this.tuning = tuning;
      this.callbacks = callbacks;
      this.root = document.getElementById("hud-root");
      this.dialogRoot = document.getElementById("dialog-root");
      this.listeners = [];
      this.reportButton = null;
      this.reportDialog = null;
      this.reportText = null;
      this.reportStatus = null;
      this.reportSend = null;
      this.answer = null;
      this.send = null;
      this.equation = null;
      this.problemMirror = null;
      this.feedback = null;
      this.progress = null;
      this.previousFocus = null;
    }

    listen(element, event, handler, options) {
      element.addEventListener(event, handler, options);
      this.listeners.push(function () {
        element.removeEventListener(event, handler, options);
      });
    }

    mount() {
      this.root.replaceChildren();
      this.dialogRoot.replaceChildren();
      const hud = document.createElement("div");
      hud.className = "hud";

      this.progress = document.createElement("div");
      this.progress.className = "progress-track";
      this.progress.setAttribute("aria-label", "Dock progress");
      this.progress.style.setProperty(
        "--dot-radius",
        this.tuning.hud.dotRadiusPx + "px"
      );
      this.progress.style.setProperty(
        "--dot-gap",
        this.tuning.hud.dotGapPx + "px"
      );
      for (let index = 0; index < C.SESSION_LENGTH; index += 1) {
        const dot = document.createElement("span");
        dot.className = "progress-dot";
        dot.setAttribute("aria-hidden", "true");
        this.progress.appendChild(dot);
      }

      this.equation = document.createElement("div");
      this.equation.className = "equation-banner";
      this.equation.setAttribute("aria-hidden", "true");
      this.problemMirror = document.createElement("p");
      this.problemMirror.className = "sr-only";
      this.problemMirror.setAttribute("aria-live", "polite");

      const answerPanel = document.createElement("div");
      answerPanel.className = "answer-panel";
      const form = document.createElement("form");
      form.className = "answer-form";
      form.autocomplete = "off";
      form.noValidate = true;
      const label = document.createElement("label");
      label.className = "sr-only";
      label.htmlFor = "answer";
      label.textContent = "Answer";
      this.answer = document.createElement("input");
      this.answer.id = "answer";
      this.answer.name = "answer";
      this.answer.type = "text";
      this.answer.inputMode = "numeric";
      this.answer.pattern = "[0-9]*";
      this.answer.maxLength = 4;
      this.send = document.createElement("button");
      this.send.className = "primary";
      this.send.type = "submit";
      this.send.textContent = "Send";
      form.append(label, this.answer, this.send);
      this.feedback = document.createElement("p");
      this.feedback.className = "feedback-slot";
      this.feedback.setAttribute("aria-live", "polite");
      answerPanel.append(form, this.feedback);

      this.reportButton = document.createElement("button");
      this.reportButton.className = "report-button";
      this.reportButton.type = "button";
      this.reportButton.textContent = "Report a problem";
      hud.append(this.progress, this.equation, this.problemMirror, answerPanel);
      this.root.appendChild(hud);
      this.root.appendChild(this.reportButton);

      this.reportDialog = document.createElement("div");
      this.reportDialog.className = "report-dialog";
      this.reportDialog.hidden = true;
      this.reportDialog.setAttribute("role", "dialog");
      this.reportDialog.setAttribute("aria-modal", "true");
      this.reportDialog.setAttribute("aria-labelledby", "report-label");
      const reportLabel = document.createElement("label");
      reportLabel.id = "report-label";
      reportLabel.htmlFor = "report-text";
      reportLabel.textContent = "What went wrong?";
      this.reportText = document.createElement("textarea");
      this.reportText.id = "report-text";
      this.reportText.rows = 3;
      this.reportText.maxLength = 300;
      const reportActions = document.createElement("div");
      reportActions.className = "report-actions";
      const reportCancel = document.createElement("button");
      reportCancel.type = "button";
      reportCancel.textContent = "Close";
      this.reportSend = document.createElement("button");
      this.reportSend.type = "button";
      this.reportSend.className = "primary";
      this.reportSend.textContent = "Send";
      reportActions.append(reportCancel, this.reportSend);
      this.reportStatus = document.createElement("p");
      this.reportStatus.className = "report-status";
      this.reportStatus.setAttribute("aria-live", "polite");
      this.reportDialog.append(
        reportLabel,
        this.reportText,
        reportActions,
        this.reportStatus
      );
      this.dialogRoot.appendChild(this.reportDialog);

      this.listen(form, "submit", (event) => {
        event.preventDefault();
        this.callbacks.onAnswer(this.answer.value);
      });
      this.listen(this.answer, "input", () => {
        this.callbacks.onActivity();
      });
      this.listen(this.reportButton, "click", () => this.openReport());
      this.listen(reportCancel, "click", () => this.closeReport());
      this.listen(this.reportSend, "click", () => this.sendReport());
      this.listen(this.reportDialog, "keydown", (event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          this.closeReport();
          return;
        }
        if (event.key !== "Tab") return;
        const focusable = this.focusableReportElements();
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      });
    }

    focusableReportElements() {
      return Array.from(
        this.reportDialog.querySelectorAll(
          "button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex='-1'])"
        )
      );
    }

    openReport() {
      this.previousFocus = document.activeElement;
      this.reportDialog.hidden = false;
      this.reportStatus.textContent = "";
      this.reportText.focus();
    }

    closeReport() {
      this.reportDialog.hidden = true;
      this.reportText.value = "";
      this.reportStatus.textContent = "";
      if (this.reportButton) this.reportButton.focus();
    }

    async sendReport() {
      const description = this.reportText.value.trim();
      if (!description) return;
      this.reportSend.disabled = true;
      const sent = await this.callbacks.onReport(description);
      this.reportSend.disabled = false;
      this.reportStatus.textContent = sent ? "Sent. Thanks." : "Could not send.";
      if (sent) this.reportText.value = "";
    }

    setQuestion(question) {
      if (!question) {
        this.equation.textContent = "";
        this.problemMirror.textContent = "";
        return;
      }
      this.clearAnswer();
      const equation =
        question.operands[0] + " " + question.operator + " " + question.operands[1];
      this.equation.textContent = equation;
      this.problemMirror.textContent = equation;
      this.focusAnswer();
    }

    setProgress(answered) {
      Array.from(this.progress.children).forEach(function (dot, index) {
        dot.classList.toggle("filled", index < answered);
      });
    }

    setFeedback(text, tone) {
      this.feedback.textContent = text;
      this.feedback.className = "feedback-slot " + (tone || "");
    }

    setSendEnabled(enabled) {
      this.send.disabled = !enabled;
    }

    clearAnswer() {
      this.answer.value = "";
    }

    focusAnswer() {
      this.answer.focus();
    }

    unmount() {
      this.listeners.forEach(function (remove) {
        remove();
      });
      this.listeners = [];
      this.root.replaceChildren();
      this.dialogRoot.replaceChildren();
      this.reportButton = null;
      this.reportDialog = null;
    }
  }

  window.Hud = Hud;
})();
