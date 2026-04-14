function openContent(event, tabName) {
  // Declare variables
  let i, tabcontent, tablinks;

  // Get all elements with class="tabcontent" and hide them
  tabcontent = document.getElementsByClassName("tabcontent");
  for (i = 0; i < tabcontent.length; i++) {
    tabcontent[i].style.display = "none";
  }

  // Get all elements with class="tablinks" and remove the class "active"
  tablinks = document.getElementsByClassName("tablinks");
  for (i = 0; i < tablinks.length; i++) {
    tablinks[i].className = tablinks[i].className.replace(" active", "");
  }

  // Show the current tab, and add an "active" class to the button that opened the tab
  document.getElementById(tabName).style.display = "block";
  event.currentTarget.className += " active";
}
document.getElementById("content").style.backgroundImage = "none";
// Open study description tab on page load. Get the element with id="defaultOpen" and click on it
document.getElementById("defaultOpen").click();

// In the case the study guide contains only two tabs set their width to 50% instead of the 1/3
// set in style.css
let tabLinks = document
  .getElementsByClassName("tab")[0]
  .getElementsByClassName("tablinks");

if (tabLinks.length == 2) {
  tabLinks[0].style.width = "50%";
  tabLinks[1].style.width = "50%";
}

// This sorting function is called when user clicks on a column header in the variable table
function sortTable(nth) {
  var table, expandable_rows, expansion_rows, thisCol, invert, cols;

  table = document.getElementById("var_table");

  // Table rows with class 'expandable' are always visible
  expandable_rows = table.getElementsByClassName("expandable");

  // Table rows with class 'expansion' contain the content that can be toggled visible or hidden by clicking
  // their respective 'expandable' row
  expansion_rows = table.getElementsByClassName("expansion");

  cols = table.getElementsByTagName("tr")[0].getElementsByTagName("TH");

  // Function parameter nth refers to nth column that was clicked
  thisCol = cols[nth];

  // Clear incr/desc_order classes from other columns
  for (i = 0; i < cols.length; i++) {
    if (thisCol != cols[i]) {
      cols[i].classList.remove("incr_order");
      cols[i].classList.remove("desc_order");
    }
  }

  // If the clicked column was previously sorted in increasing order, sort it in descending (inverted) order
  if (thisCol.classList.contains("incr_order")) {
    invert = true;
    thisCol.classList.remove("incr_order");
    thisCol.classList.add("desc_order");
  }

  // Sort the column in increasing order if it previously was sorted in descending order or not sorted at all
  else {
    invert = false;
    thisCol.classList.remove("desc_order");
    thisCol.classList.add("incr_order");
  }

  // Temporary array for storing HTML row objects in sorted order
  var store = [];

  for (var i = 0; i < expandable_rows.length; i++) {
    var expandable_row = expandable_rows[i];
    var expansion_row = expansion_rows[i];

    // Store the content of the field to be used in sorting
    var key = expandable_row.cells[nth].textContent;

    // Store the content used in sorting and references to its respective table row objects
    store.push([key, [expandable_row, expansion_row]]);
  }

  store.sort(function (x, y) {
    // Nth = 2 means variable name column was clicked
    if (nth == 2) {
      // x[0] and y[0] contains the keys in the store array
      // perform comparison in lower-case for case-insensitivity
      x = x[0].toLowerCase();
      y = y[0].toLowerCase();
    } else if (nth == 1) {
      // For variable ID sort use collator for natural ordering of strings consisting of numbers and letters
      const collator = new Intl.Collator(undefined, {
        numeric: true,
        sensitivity: "base",
      });
      x = x[0];
      y = y[0];
      if (!invert) return collator.compare(x, y);
      else return collator.compare(y, x);
    } else if (nth == 0) {
      // For sorting the order of appearance column convert the keys to int
      x = +x[0];
      y = +y[0];
    }

    if (x < y) {
      if (!invert) return -1;
      else return 1;
    } else if (x > y) {
      if (!invert) return 1;
      else return -1;
    } else {
      return 0;
    }
  });

  // Append the table element with expandable and expansion rows from the store array that now contains the
  // objects in correct order
  for (var i = 0; i < store.length; i++) {
    table.appendChild(store[i][1][0]);
    table.appendChild(store[i][1][1]);
  }

  store = null;
}

// Add event listeners to variable table for toggling content
function expand_rows() {
  // Variable table rows that can be expanded
  var expandable_rows = document.getElementsByClassName("expandable");

  var i;

  for (i = 0; i < expandable_rows.length; i++) {
    // Add click event listener to every expandable row
    expandable_rows[i].addEventListener("click", function () {
      // nextElementSibling is the table row that is shown upon clicking the respective expandable row
      var expanded_tr = this.nextElementSibling;
      if (expanded_tr.style.display === "table-row") {
        expanded_tr.style.display = "none";
        this.classList.remove("active");
      } else {
        expanded_tr.style.display = "table-row";
        this.classList.add("active");
      }
    });
  }
}
expand_rows();

// Add event listeners on the front page of study guide for toggling content (accordion menu)
// Maybe combine this with expand_rows() as they're nearly identical?
function expand_items() {
  var items = document.getElementsByClassName("item");

  var i;

  for (i = 0; i < items.length; i++) {
    if (i == 0) {
      items[i].nextElementSibling.style.display = "block";
      items[i].classList.add("active");
    }
    items[i].addEventListener("click", function () {
      var itemContent = this.nextElementSibling;
      if (itemContent.style.display === "block") {
        itemContent.style.display = "none";
        this.classList.remove("active");
      } else {
        itemContent.style.display = "block";
        this.classList.add("active");
      }
    });
  }
}
expand_items();

// Expand all the variable-specific content in variable table
function var_toggle() {
  var btn = document.getElementById("var_toggle");
  var bclasses = btn.classList;

  // Take an active search filter into account. Don't expand content that is currently hidden
  // by the search filter. Var_search() returns visible expandable table rows
  var var_rows = var_search()
    ? var_search()
    : document.getElementsByClassName("expandable");
  var row;

  for (i = 0; i < var_rows.length; i++) {
    row = var_rows[i];

    // Show all content. Mark all visible 'expandable' rows as active and display their respective 'expansion'
    // row
    if (bclasses.contains("show")) {
      if (!row.classList.contains("active")) {
        row.classList.add("active");
        row.nextElementSibling.style.display = "table-row";
      }
    }

    // Hide all previously expanded content
    else {
      if (row.classList.contains("active")) {
        row.classList.remove("active");
        row.nextElementSibling.style.display = "none";
      }
    }
  }

  // Alternate the behavior (by applying or removing class 'show') and the text of the button
  bclasses.toggle("show");

  // Take the new button text value from its name attribute and set the old text value as the name attribute's value
  let newBtnText = btn.getAttribute("name");
  btn.setAttribute("name", btn.textContent);
  btn.textContent = newBtnText;
}

// Expand all header items on the front page
// Maybe combine this with var_toggle() as they're nearly identical?
function item_toggle() {
  var btn = document.getElementById("item_toggle");
  var bclasses = btn.classList;

  var items = document.getElementsByClassName("item");
  var item;

  for (i = 0; i < items.length; i++) {
    item = items[i];
    if (bclasses.contains("show")) {
      if (!item.classList.contains("active")) {
        item.classList.add("active");
        item.nextElementSibling.style.display = "block";
      }
    } else {
      if (item.classList.contains("active")) {
        item.classList.remove("active");
        item.nextElementSibling.style.display = "none";
      }
    }
  }

  bclasses.toggle("show");

  let newBtnText = btn.getAttribute("name");
  btn.setAttribute("name", btn.textContent);
  btn.textContent = newBtnText;
}

// Filter search for variable table that is called when the search input field is changed
function var_search(e) {
  // Input field
  var input = document.getElementById("var_search");

  // Input field value (in lower case for case-insensitivity)
  var query = input.value.toLowerCase();

  // Fields from each column
  var var_names = document.getElementsByClassName("var_name");
  var var_labels = document.getElementsByClassName("var_label");
  var var_questions = document.getElementsByClassName("question_text");

  var searchFrom;

  var cb = document.getElementsByName("var_filter");
  var checked_value;

  // Get the type of search (variable name search, var id search, question text search)
  for (var i = 0; i < cb.length; i++) {
    if (cb[i].checked) checked_value = cb[i].value;
  }

  // Storage for displayed row objects
  var results = [];

  if (!query && !e) {
    return 0;
  } else {
    // Loop through all variable table rows
    for (i = 0; i < var_names.length; i++) {
      if (checked_value == "var_name") searchFrom = var_names[i].textContent;
      else if (checked_value == "var_label") searchFrom = var_labels[i].textContent;
      else searchFrom = var_questions[i].textContent;

      var table_row = var_names[i].parentNode;
      var expanded_row = table_row.nextElementSibling;

      // If there is no match between query and content, hide the respective table rows
      if (searchFrom.toLowerCase().indexOf(query) < 0) {
        table_row.style.display = "none";
        expanded_row.style.display = "none";
      }

      //If there is a match, make sure the respective expandable table row is visible
      else {
        table_row.style.display = "";

        // If the expandable row was previously expanded, display the respective expansion row
        if (table_row.classList.contains("active")) {
          expanded_row.style.display = "table-row";
        } else {
          expanded_row.style.display = "";
        }
        results.push(table_row);
      }
    }
    //Return list of visible rows for other use
    return results;
  }
}

// When scrolled down enough, display a button that takes the user to the top of the page on click

window.onscroll = function () {
  displayScrollBtn();
};

function displayScrollBtn() {
  let button = document.getElementById("arrow_up");
  if (
    document.body.scrollTop > 300 ||
    document.documentElement.scrollTop > 300
  ) {
    button.style.display = "block";
  } else {
    button.style.display = "none";
  }
}

function takeUp() {
  document.body.scrollTop = 0;
  document.documentElement.scrollTop = 0;
}
