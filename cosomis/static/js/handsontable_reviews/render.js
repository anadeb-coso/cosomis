// Définitions des éditeurs et renderers personnalisés pour Handsontable


// Éditeur personnalisé pour la sélection multiple avec cases à cocher et filtre
class MultiSelectCheckboxEditor extends Handsontable.editors.BaseEditor {
    
    constructor(hotInstance) {
        super(hotInstance);
        
        // 1. Conteneur principal
        this.container = document.createElement('div');
        this.container.classList.add('multi-select-editor-popup');
        this.container.style.position = 'absolute';
        this.container.style.zIndex = '1000';
        this.container.style.backgroundColor = '#fff';
        this.container.style.border = '1px solid #ccc';
        this.container.style.padding = '8px';
        this.container.style.maxHeight = '200px';
        this.container.style.overflowY = 'auto';
        this.container.style.boxShadow = '0 4px 8px rgba(0,0,0,0.1)';
        this.container.style.display = 'none'; 
        
        // 2. Champ de filtre (Nouveau)
        this.filterInput = document.createElement('input');
        this.filterInput.type = 'text';
        this.filterInput.placeholder = 'Rechercher une option...';
        this.filterInput.style.width = 'calc(100% - 16px)';
        this.filterInput.style.marginBottom = '8px';
        
        // Conteneur pour les cases à cocher (pour le défilement)
        this.checkboxContainer = document.createElement('div');
        
        this.container.appendChild(this.filterInput);
        this.container.appendChild(this.checkboxContainer);
        
        document.body.appendChild(this.container);
        
        this.selectedIds = []; 
        this.allOptions = []; // Stocke toutes les options pour le filtrage
    }

    /**
    * Appelé pour préparer l'éditeur. Configure la liste des options.
    * @param {*} originalValue - Le tableau d'IDs M2M actuel.
    * @param {*} cellProperties - Contient mapSource (clé de la relation).
    */
    prepare(row, col, prop, td, originalValue, cellProperties) {
        super.prepare(row, col, prop, td, originalValue, cellProperties);
        
        // La clé pour la carte des options (ex: 'tags')
        this.mapKey = cellProperties.mapSource; 
        this.options_source = cellProperties.source;
        
        // La valeur actuelle doit être un tableau d'IDs
        this.selectedIds = Array.isArray(originalValue) ? originalValue : [];
        
        this._renderOptions();
    }

    /**
    * Génère les cases à cocher dans le conteneur.
    */
    _renderOptions() {
        this.checkboxContainer.innerHTML = '';
        const allOptions = this.options_source//getOptionsArray(this.mapKey);

        // Stocke toutes les options pour le filtrage
        this.allOptions = allOptions;

        if (this.allOptions.length === 0) {
            this.checkboxContainer.innerHTML = '<div>Aucune option disponible.</div>';
            return;
        }
        // Afficher toutes les options initialement
        this._filterOptions('');

        // Stopper la propagation pour ne pas fermer l'éditeur en cliquant/tapant
        this.container.onmousedown = (e) => e.stopPropagation();
        this.filterInput.onmousedown = (e) => e.stopPropagation();

    }


    /**
    * Filtre les options basées sur le texte de recherche.
    */
    _filterOptions(searchText) {
        this.checkboxContainer.innerHTML = '';
        const lowerSearchText = searchText.toUpperCase();
        
        const filteredOptions = this.allOptions.filter(option => 
            option.toUpperCase().includes(lowerSearchText)
        );
        //console.log("filteredOptions", filteredOptions)

        if (filteredOptions.length === 0) {
            this.checkboxContainer.innerHTML = '<div>Aucun résultat pour cette recherche.</div>';
            return;
        }

        filteredOptions.forEach(option => {
            //console.log('option', option);
            const isChecked = this.selectedIds.includes(option);
            
            const label = document.createElement('label');
            label.style.display = 'block';
            label.style.whiteSpace = 'nowrap';
            label.style.padding = '2px 0';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = option;
            checkbox.checked = isChecked;
            checkbox.style.marginRight = '5px';
            
            checkbox.setAttribute('data-id', option); 

            // IMPORTANT : L'état de la checkbox est mis à jour dans le this.selectedIds
            // afin de persister la sélection même si l'option est filtrée.
            checkbox.addEventListener('change', () => {
                const id = checkbox.getAttribute('data-id');
                if (checkbox.checked) {
                    if (!this.selectedIds.includes(id)) {
                        this.selectedIds.push(id);
                    }
                } else {
                    this.selectedIds = this.selectedIds.filter(selectedId => selectedId !== id);
                }
            });

            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(option));
            this.checkboxContainer.appendChild(label);

        });
    }

    
    /**
    * Ouvre l'éditeur et le positionne.
    */
    open() {
        const coords = this.instance.getCell(this.row, this.col);
        const cellBounding = this.instance.getCell(this.row, this.col).getBoundingClientRect();
        const containerBounding = this.instance.rootElement.getBoundingClientRect();
        
        // Positionnement juste sous la cellule
        this.container.style.top = (cellBounding.bottom + window.scrollY) + 'px';
        this.container.style.left = (cellBounding.left + window.scrollX) + 'px';
        this.container.style.minWidth = cellBounding.width + 'px';
        
        this.container.style.display = 'block';
        
        // Focus est mis sur le premier élément pour permettre le défilement
        const firstCheckbox = this.checkboxContainer.querySelector('input[type="checkbox"]');
        if (firstCheckbox) {
            firstCheckbox.focus();
        }        
        
        // Vider le champ de filtre et lui donner le focus
        this.filterInput.value = '';
        this.filterInput.focus();
        this._filterOptions(''); // Rétablir toutes les options au cas où elles étaient filtrées

        // CLÉ : Écouter la saisie de l'utilisateur pour filtrer
        this.filterInput.oninput = () => this._filterOptions(this.filterInput.value);

    }

    /**
    * Ferme l'éditeur.
    */
    close() {
        this.container.style.display = 'none';
    }
    
    /**
    * Récupère la valeur finale à stocker dans la cellule.
    * @returns {Array<number>} Le tableau des IDs sélectionnés.
    */
    getValue() {
        /*const selectedIds = [];
        const checkboxes = this.checkboxContainer.querySelectorAll('input[type="checkbox"]');
        
        checkboxes.forEach(checkbox => {
            if (checkbox.checked) {
                // Récupère l'ID stocké dans l'attribut data-id
                selectedIds.push(checkbox.getAttribute('data-id')); 
            }
        });
        
        return selectedIds;*/
        return this.selectedIds.filter(selected => selected !== '');
    }
    
    // --- Méthodes requises pour Handsontable, laissées vides ou par défaut ---
    focus() { /* Ne fait rien, car le focus est géré par la boîte de dialogue */ }
    
    // Si la valeur est modifiée, nous n'avons rien à faire, nous la lisons dans getValue().
    setValue() {} 
    
    // Méthode appelée lorsque l'utilisateur appuie sur Entrée ou Tab
    keydown(event) {
        // En appuyant sur Entrée ou Échap, on valide ou annule la modification
        if (event.key === 'Enter' || event.key === 'Escape') {
            this.instance.view.editorManager.closeEditorAndSaveChanges(event.key === 'Enter');
            event.stopImmediatePropagation();
        }
    }
}



// --- Renderer pour les champs de sélection multiple ---
function generic_multi_select_renderer(instance, td, row, col, prop, value, cellProperties) {
                
    // 1. Appel du renderer de base pour les propriétés visuelles (styles, classes, etc.)
    Handsontable.renderers.TextRenderer.apply(this, arguments);
    
    // Si la valeur est nulle ou vide, on affiche une chaîne vide et on s'arrête
    if (value === null || typeof value === 'undefined' || value.length === 0) {
        td.innerText = '';
        return td;
    }
    //columnDefinitions
    const mapKey = cellProperties.mapSource; 

    if (!mapKey || !cellProperties.source) {
        // Si la carte n'est pas trouvée, afficher la valeur telle quelle (tableau joint ou ID)
        td.innerText = Array.isArray(value) ? value.join(', ') : String(value);
        return td;
    }
    
    const currentMap = cellProperties.source;
    let idsToRender = [];
    // 2. Détermination du type de valeur (Tableau d'IDs ou Chaîne d'IDs)
    if (Array.isArray(value)) {
        // Cas A: La valeur est déjà un tableau d'IDs (Format préféré)
        idsToRender = value;
    } else if (typeof value === 'string' && value.includes(',')) {
        // Cas B: La valeur est une chaîne d'IDs (Potentiellement laissée par un éditeur)
        idsToRender = value
            .split(',')
            .map(item => item.trim())
            .filter(item => item !== '');
    } else {
        // Cas C: Valeur simple (pour FK ou autres champs numériques)
        idsToRender = [value]; // On traite comme un tableau d'un seul élément
    }
    
    // 3. Rendu final
    if (idsToRender.length > 0) {
        const displayNames = idsToRender.map(item => currentMap.find(x => x === item.toUpperCase()) || item.toUpperCase());
        // On affiche les noms séparés par des virgules
        td.innerText = displayNames.join(', '); 
    } else {
        td.innerText = '';
    }

    return td;
}
// --- Fin du Renderer ---



// --- Renderer pour les champs de sélection simple ---
function select_renderer(instance, td, row, col, prop, value, cellProperties) {
    // Le 'value' que nous recevons ici est l'ID de l'objet lié (ex: Project_id: 5)
    
    // Si la valeur est null ou undefined, affichez une cellule vide
    if (value === null || typeof value === 'undefined') {
        Handsontable.renderers.TextRenderer.apply(this, arguments);
        return td;
    }
    
    Handsontable.renderers.TextRenderer.apply(this, arguments); 

    // Ajoutez ici la logique spécifique pour le style du 'select'
    td.style.backgroundColor = '#f0f8ff'; // Exemple: Couleur de fond pour les champs de sélection
    
    return td;
}
// --- Fin du Renderer ---


// --- Renderer pour le format monétaire en CFA ---
function currency_renderer(instance, td, row, col, prop, value, cellProperties) {
    if (value === null || value === undefined) {
        value = '';
    } else {
        const formatter = new Intl.NumberFormat('fr-FR', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        });
        value = formatter.format(value) + ' CFA'; 
    }
    Handsontable.renderers.TextRenderer.apply(this, arguments);
    td.innerText = value;
} 
// --- Fin du Renderer ---