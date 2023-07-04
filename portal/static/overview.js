fetch('/api/builds', { cache: "reload" })
    .then((response) => response.json())
    .then((builds) => {
        const builds_table_content = document.getElementById('builds_table_content');

        for (const build of builds) {
            const row = document.createElement("div");
            row.classList.add("table-row");

            const row_filename = document.createElement("div");
            row_filename.classList.add("table-body-cell");
            row_filename.innerHTML = "<a href='/build/" + build['id'] + "'><pre>" + build['filename'] + "</pre></a>";
            row.appendChild(row_filename);

            builds_table_content.appendChild(row);
        }
    })

fetch('/api/statistics', { cache: "reload" })
    .then((response) => response.json())
    .then((statistics) => {
        function fill_statistic(element_id, value) {
            let element = document.getElementById(element_id);
            element.innerHTML = value;
        }

        fill_statistic("stat_build_count_known", statistics["build_count_known"])
        fill_statistic("stat_build_count_stored", statistics["build_count_stored"])
        fill_statistic("stat_build_size_stored", human_readable_size(statistics["build_size_stored"]))
        fill_statistic("stat_device_count", statistics["device_count"])
        fill_statistic("stat_device_version_count", statistics["device_version_count"])
        fill_statistic("stat_build_size_average", human_readable_size(statistics["build_size_average"]))
        fill_statistic("stat_build_size_total", human_readable_size(statistics["build_size_average"] * statistics["device_version_count"]))
    })
