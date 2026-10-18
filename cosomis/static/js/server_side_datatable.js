/* Server-side DataTables for the list pages (see cosomis/datatables.py), with
 * the same behaviour as the /investments/ list of the local development portal:
 *  - each page of rows is fetched from the current URL + ?format=datatables, so
 *    the filters of the query string apply to every page;
 *  - a skeleton overlay covers the rows while a page loads, and filter forms
 *    re-arm it on submit so stale rows never linger during the reload;
 *  - "Choose the columns to display" switches toggle the matching column;
 *  - an element of a cell with data-row-class="x" adds the class x to its row;
 *  - optional row selection kept across pages: tick rows on several pages, or
 *    tick the header box to select every result of the filters. The selection is
 *    posted as `all_queryset` (true/false) + `selected_ids` (ids whose state
 *    differs from that baseline, joined with "-").
 */
(function (window, $) {
    "use strict";

    var MIN_OVERLAY_MS = 400;

    function datatableUrl() {
        var url = new URL(window.location.href);
        url.hash = "";
        url.searchParams.set("format", "datatables");
        return url.toString();
    }

    function formatNumber(value) {
        return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    }

    function setupOverlay(table, $stage) {
        var $overlay = $stage.find(".table-loading-overlay");
        var shownAt = 0;

        function align() {
            var $thead = $stage.find("thead").first();
            if (!$overlay.length || !$thead.length) return;
            var top = $thead.offset().top + $thead.outerHeight() - $stage.offset().top;
            $overlay.css("top", Math.max(0, top) + "px");
        }

        function show() {
            shownAt = Date.now();
            $overlay.addClass("is-active");
            align();
        }

        function hide() {
            var wait = Math.max(0, MIN_OVERLAY_MS - (Date.now() - shownAt));
            window.setTimeout(function () { $overlay.removeClass("is-active"); }, wait);
        }

        table.on("processing.dt", function (e, settings, processing) {
            if (processing) show(); else hide();
        });
        table.on("init.dt draw.dt", align);
        $(window).on("resize", align);
        return {show: show, hide: hide};
    }

    function setupSelection(table, opts) {
        var $form = $(opts.form);
        var $selectAll = $(opts.selectAll);
        var allMode = false;  // true: every result of the filters, minus `toggled`
        var toggled = [];
        var total = 0;

        function count() {
            return allMode ? Math.max(total - toggled.length, 0) : toggled.length;
        }

        function sync() {
            $form.find('input[name="all_queryset"]').val(allMode ? "true" : "false");
            $form.find('input[name="selected_ids"]').val(toggled.join("-"));
            $(opts.counter).text(formatNumber(count()));
            var all = allMode && toggled.length === 0 && total > 0;
            $selectAll.prop("checked", all).prop("indeterminate", !all && count() > 0);
        }

        function rowChecks() {
            return $(table.table().body()).find(opts.rowCheck);
        }

        table.on("xhr.dt", function (e, settings, json) {
            if (json) total = json.recordsFiltered;
            sync();
        });

        // Paging rebuilds every checkbox: re-apply the selection already made.
        table.on("draw.dt", function () {
            rowChecks().each(function () {
                var inList = toggled.indexOf(this.value) !== -1;
                this.checked = inList ? !allMode : allMode;
            });
            sync();
        });

        $(table.table().body()).on("change", opts.rowCheck, function () {
            var index = toggled.indexOf(this.value);
            if (this.checked !== allMode) {
                if (index === -1) toggled.push(this.value);
            } else if (index !== -1) {
                toggled.splice(index, 1);
            }
            sync();
        });

        $selectAll.on("change", function () {
            allMode = this.checked;
            toggled = [];
            rowChecks().prop("checked", allMode);
            sync();
        });

        $form.on("submit", function (e) {
            sync();
            if (count() === 0) {
                e.preventDefault();
                // disableOnSubmit.js has already disabled the submit buttons.
                window.setTimeout(function () { $form.find(":submit").prop("disabled", false); }, 0);
                window.alert(opts.emptyMessage);
            }
        });
    }

    function init(options) {
        var $table = $(options.table);
        var $stage = $table.closest(".dt-table-stage");

        $.fn.dataTable.ext.errMode = "none";
        var config = $.extend(true, {}, options.config, {
            ajax: {url: datatableUrl()},
            autoWidth: false,
            // A cell can style its whole row: <span data-row-class="...">.
            createdRow: function (row) {
                $(row).find("[data-row-class]").each(function () {
                    $(row).addClass($(this).data("row-class"));
                });
            }
        });
        if (options.languageUrl) config.language = {url: options.languageUrl};

        var table = $table.DataTable(config);
        var overlay = setupOverlay(table, $stage);

        table.on("xhr.dt", function (e, settings, json) {
            if (json) {
                $(options.resultsCount || ".dt-results-count").text(formatNumber(json.recordsFiltered));
                if (options.onData) options.onData(json);
            }
        });
        table.on("error.dt", function () {
            overlay.hide();
            $(options.resultsCount || ".dt-results-count").text("—");
            if (options.errorMessage) window.alert(options.errorMessage);
        });

        $(options.columnSwitches || ".column-switch").on("change", function () {
            table.column($(this).data("column")).visible($(this).is(":checked"));
            table.columns.adjust();
            if (table.responsive) table.responsive.recalc();
        });

        // Filters submit with a full page reload: show the loading state at once.
        $(options.filterForms || ".dt-filter-form").on("submit", function () {
            overlay.show();
        });

        if (options.selection) setupSelection(table, options.selection);
        return table;
    }

    // "How to use this table" alerts stay closed once dismissed.
    $(function () {
        $(".alert-instructions[data-storage-key]").each(function () {
            var $alert = $(this);
            var key = $alert.data("storage-key");
            try {
                if (window.localStorage.getItem(key) === "1") {
                    $alert.remove();
                    return;
                }
            } catch (e) { /* storage unavailable: show the alert */ }
            $alert.on("closed.bs.alert", function () {
                try { window.localStorage.setItem(key, "1"); } catch (e) { /* noop */ }
            });
        });
    });

    window.ServerSideDatatable = {init: init};
})(window, jQuery);
