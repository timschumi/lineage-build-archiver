const device_table_map = new Map();

fetch('/api/builds', { cache: "reload" })
    .then((response) => response.json())
    .then((builds) => {
        for (const build of builds) {
            if (!device_table_map.has(build['device'])) {
                const table = document.createElement("div");
                table.classList.add("table");

                const header = document.createElement("div");
                header.classList.add("table-header");

                const title = document.createElement("div");
                title.classList.add("table-header-cell");
                title.innerHTML = build['device'];

                const body = document.createElement("div");
                body.classList.add("table-body");

                header.appendChild(title);
                table.appendChild(header);
                table.appendChild(body);

                device_table_map.set(build['device'], table);
            }

            const device_table_body = device_table_map.get(build['device']).children[1];

            const row = document.createElement("div");
            row.classList.add("table-row");

            const row_filename = document.createElement("div");
            row_filename.classList.add("table-body-cell");
            row_filename.innerHTML = "<a class='monospace nowrap' href='/build/" + build['id'] + "'>" + build['filename'] + "</a>";
            row.appendChild(row_filename);

            device_table_body.appendChild(row);
        }

        const device_table_map_sorted = new Map([...device_table_map.entries()].sort((a, b) => a[0].localeCompare(b[0], undefined, { sensitivity: 'base' })));

        const device_list = document.getElementById('device_list');
        device_table_map_sorted.forEach((value) => {
            device_list.appendChild(value);
        });
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
