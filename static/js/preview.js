document.addEventListener("DOMContentLoaded", function () {
    /**
     * Affiche ou masque la section de prévisualisation.
     * @param {boolean} show - true pour afficher, false pour masquer.
     */
    window.togglePreview = function (show) {
      const previewContainer = document.querySelector('.preview-container');
      if (show) {
        previewContainer.style.display = 'block';
        refreshPreview();
      } else {
        previewContainer.style.display = 'none';
      }
    };
  
    /**
     * Rafraîchit le contenu de l'iframe de prévisualisation.
     * On suppose qu'une URL dédiée renvoie le HTML généré pour le payroll.
     */
    window.refreshPreview = function () {
      const previewFrame = document.getElementById('preview-frame');
      const scaleSelect = document.getElementById('preview-scale');
      const scale = scaleSelect ? parseFloat(scaleSelect.value) : 1;
  
      // URL de l'endpoint de prévisualisation (à adapter selon votre configuration)
      // Vous pouvez créer une vue Django qui renvoie le rendu de votre payroll
      previewFrame.src = "/payroll/preview/";
  
      // Une fois le contenu chargé, on applique l'échelle
      previewFrame.onload = function () {
        const body = previewFrame.contentDocument.body;
        body.style.transform = `scale(${scale})`;
        body.style.transformOrigin = "top left";
      };
    };
  
    // Rafraîchit la prévisualisation lors du clic sur le bouton "Refresh"
    const refreshButton = document.getElementById('refresh-preview');
    if (refreshButton) {
      refreshButton.addEventListener("click", refreshPreview);
    }
  
    // Met à jour l'échelle de la prévisualisation lors du changement de sélection
    const scaleSelect = document.getElementById('preview-scale');
    if (scaleSelect) {
      scaleSelect.addEventListener("change", function () {
        const previewFrame = document.getElementById('preview-frame');
        const scale = parseFloat(scaleSelect.value);
        if (previewFrame && previewFrame.contentDocument && previewFrame.contentDocument.body) {
          previewFrame.contentDocument.body.style.transform = `scale(${scale})`;
        }
      });
    }
  });
  