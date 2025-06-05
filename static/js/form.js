document.addEventListener("DOMContentLoaded", function () {
    // --- Gestion de l'ajout de services ---
  
    // Fonction qui ajoute une nouvelle ligne pour un service
    function addServiceRow() {
      let tbody = document.getElementById("services-tbody");
      let row = document.createElement("tr");
  
      row.innerHTML = `
        <td><input type="date" name="service_date[]" class="form-input"></td>
        <td><input type="text" name="service_client[]" class="form-input"></td>
        <td><input type="text" name="service_sourceLanguage[]" class="form-input"></td>
        <td><input type="text" name="service_targetLanguage[]" class="form-input"></td>
        <td><input type="number" step="0.01" name="service_duration[]" class="form-input"></td>
        <td><input type="number" step="0.01" name="service_rate[]" class="form-input"></td>
        <td><input type="number" step="0.01" name="service_amount[]" class="form-input" readonly></td>
        <td><button type="button" class="remove-service-btn">Remove</button></td>
      `;
  
      // Ajoute la ligne dans le tbody
      tbody.appendChild(row);
  
      // Gestion du bouton "Remove" pour supprimer la ligne
      row.querySelector(".remove-service-btn").addEventListener("click", function () {
        row.remove();
      });
  
      // Fonction de calcul du montant : duration * rate
      let durationInput = row.querySelector('input[name="service_duration[]"]');
      let rateInput = row.querySelector('input[name="service_rate[]"]');
      let amountInput = row.querySelector('input[name="service_amount[]"]');
  
      function calculateAmount() {
        let duration = parseFloat(durationInput.value) || 0;
        let rate = parseFloat(rateInput.value) || 0;
        amountInput.value = (duration * rate).toFixed(2);
      }
  
      // Ajout des écouteurs d'événements pour recalculer le montant à chaque changement
      durationInput.addEventListener("input", calculateAmount);
      rateInput.addEventListener("input", calculateAmount);
    }
  
    // Attache l'événement sur le bouton "Add Service"
    const addServiceBtn = document.getElementById("add-service");
    if (addServiceBtn) {
      addServiceBtn.addEventListener("click", addServiceRow);
    }
  
    // --- Prévisualisation de l'image du logo ---
  
    // Sélectionne l'élément d'upload du logo et le conteneur de prévisualisation
    const logoInput = document.getElementById("id_logo");
    const logoPreviewContainer = document.getElementById("logo-preview-container");
  
    if (logoInput) {
      logoInput.addEventListener("change", function (event) {
        const file = event.target.files[0];
        if (file) {
          const reader = new FileReader();
          reader.onload = function (e) {
            logoPreviewContainer.innerHTML = `<img src="${e.target.result}" alt="Logo Preview" style="max-width: 100%; height: auto;">`;
          };
          reader.readAsDataURL(file);
        } else {
          // Efface la prévisualisation si aucun fichier n'est sélectionné
          logoPreviewContainer.innerHTML = "";
        }
      });
    }
  });
  