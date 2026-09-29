/*
 * Application form: show only the questions of the level the applicant chose.
 * Without JavaScript every question stays visible, labelled with its level, and the server
 * ignores answers for other levels — so this is a convenience, never a requirement.
 */
(function () {
  "use strict";

  var form = document.querySelector(".application-form");
  if (!form) {
    return;
  }

  function chosenLevel() {
    var checked = form.querySelector('input[name="level"]:checked');
    if (checked) {
      return checked.value;
    }
    var hidden = form.querySelector('input[type="hidden"][name="level"]');
    return hidden ? hidden.value : "";
  }

  function update() {
    var level = chosenLevel();
    form.querySelectorAll(".question[data-level]").forEach(function (question) {
      question.hidden = question.dataset.level !== level;
    });
  }

  form.addEventListener("change", function (event) {
    if (event.target.name === "level") {
      update();
    }
  });
  update();

  var errors = document.getElementById("form-errors");
  if (errors) {
    errors.focus();
  }
})();
