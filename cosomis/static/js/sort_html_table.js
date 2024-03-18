function sortTable(tableId, columnIndex) {
  alert("ok")
    var table, rows, switching, i, x, y, shouldSwitch, direction;
    table = document.getElementById(tableId);
    switching = true;
    direction = "asc"; // Default sort direction
  
    while (switching) {
      switching = false;
      rows = table.getElementsByTagName("tr");
  
      for (i = 1; i < (rows.length - 1); i++) {
        shouldSwitch = false;
        x = rows[i].getElementsByTagName("td")[columnIndex];
        y = rows[i + 1].getElementsByTagName("td")[columnIndex];
  
        if (direction === "asc") {
          if (parseInt(x.innerHTML) > parseInt(y.innerHTML)) {
            shouldSwitch = true;
            break;
          }
        } else if (direction === "desc") {
          if (parseInt(x.innerHTML) < parseInt(y.innerHTML)) {
            shouldSwitch = true;
            break;
          }
        }
      }
  
      if (shouldSwitch) {
        rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
        switching = true;
      } else {
        if (direction === "asc") {
          direction = "desc";
          switching = true;
        }
      }
    }
  }
  