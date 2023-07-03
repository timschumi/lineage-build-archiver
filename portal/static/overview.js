fetch('/api/builds', { cache: "reload" })
    .then((response) => response.json())
    .then((builds) => {
        const builds_table = document.getElementById('builds_table');

        for (const build of builds) {
            const new_row = builds_table.insertRow();
            new_row.innerHTML = "<td><a href='/build/" + build['id'] + "'><pre>" + build['filename'] + "</pre></a></td>";
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
