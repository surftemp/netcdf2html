// manage the HTML comprising grid and overlay views
// bind the controls in the views

class ImageFetcher {

    /**
     * Manage the fetching for images where the url is encoded in attribute load_url, as they become visible
     *
     * This is useful to avoid being throttled by a server with 429 errors when a lot of images are fetched at once
     */

    constructor(concurrency, callback) {
        // concurrency defines the number of fetches that can run in parallel
        this.concurrency = concurrency;
        this.pending_image_ids = new Set();
        this.queued_image_ids = [];
        this.fetching = 0;
        this.callback = callback;
    }

    submit(image_id) {
        if (!(image_id in this.pending_image_ids)) {
            this.pending_image_ids.add(image_id);
            this.queued_image_ids.push(image_id);
            if (this.fetching < this.concurrency) {
                this.start_fetching().then(() => {
                });
            }
        }
    }

    async start_fetching() {
        this.fetching += 1;
        while(this.queued_image_ids.length > 0) {
            await this.fetch(this.queued_image_ids.splice(0,1));
        }
        this.fetching -= 1;
    }

    async fetch(image_id) {
        let img = document.getElementById(image_id);
        let load_url = img.getAttribute("load_url");
        let response = await fetch(load_url);
        const blob = await response.blob();
        const buffer = await blob.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        const base64 = bytes.toBase64();
        let url = `data:image/png;base64,${base64}`;
        img.src = url;
        this.pending_image_ids.delete(image_id);
        if (this.callback) {
            this.callback(image_id, url);
        }
    }
}

class HtmlView {

    constructor() {
        this.scenes = {};
        this.index = [];
        this.current_index = 0;
        this.layer_opacities = {};
        this.months_excluded = {};

        this.di = null; // the dataimage used in the overlay view

        this.base_url = window.location.origin + window.location.pathname;

        this.root_element = document.getElementById("root_element");
        this.spinner = null;

        // locate overlay controls and other elements
        this.time_range = document.getElementById("time_index");
        this.zoom_control = document.getElementById("zoom_control");
        this.info_content = document.getElementById("info_content"); // optional, may be undefined
        this.show_layers = document.getElementById("show_layers");
        this.layer_container = document.getElementById("layer_container");
        this.next_button = document.getElementById("next_btn");
        this.prev_button = document.getElementById("prev_btn");
        this.close_all_btn = document.getElementById("close_all_sliders");
        this.show_filters = document.getElementById("show_filters");
        this.filter_container = document.getElementById("filter_container");
        this.scene_label_elt = document.getElementById("scene_label");

        this.grid_select_date = document.getElementById("grid_select_date");
        this.overlay_select_date = document.getElementById("overlay_select_date");

        /* page related controls (grid view) */

        this.prev_page_btn = document.getElementById("prev_page_btn");
        this.next_page_btn = document.getElementById("next_page_btn");
        this.page_range = document.getElementById("page_index");
        this.page_size_control = document.getElementById("page_size");

        this.page_label = document.getElementById("page_label");

        this.current_page = 0;
        this.max_page = 0;

        this.show_data = document.getElementById("show_data");
        this.data_container = document.getElementById("data_container");

        this.show_info = document.getElementById("show_info");
        this.info_container = document.getElementById("info_container");

        this.overlay_container = document.getElementById("overlay_container");
        this.grid_container = document.getElementById("grid_container");
        this.timeseries_container = document.getElementById("timeseries_container");
        this.terrain_container = document.getElementById("terrain_container");

        this.grid_view_button = document.getElementById("grid_view_btn");
        this.grid_view_button2 = document.getElementById("grid_view_btn2");
        this.timeseries_view_button = document.getElementById("timeseries_view_btn");
        this.overlay_view_button = document.getElementById("overlay_view_btn");

        this.terrain_view_button = document.getElementById("terrain_view_btn");
        this.exit_terrain_view_button = document.getElementById("exit_terrain_view");
        this.terrain_zoom = document.getElementById("terrain_zoom");
        this.terrain_zoom_value = document.getElementById("terrain_zoom_value");

        // record custom min/max/cmaps selected in overlay view for data layers only
        this.data_layers = {};

        // for each layer_group, record the current activate layer
        this.layer_group_active_layers = {};

        // record the last image url viewed in overlay mode for each layer
        this.overlay_urls = {};

        this.lm = null;

        this.timeseries_charts = null;

        if (!this.grid_container) {
            if (this.timeseries_container) {
                this.timeseries_container.style.display = "block";
                this.load_timeseries().then(() => {
                });
            }
        }

        this.tv = null; // populated with a TerrainView object when in "terrain view" mode
        if (this.terrain_zoom) {
            this.terrain_zoom_value.innerHTML = this.terrain_zoom.value;
            this.terrain_zoom.addEventListener("change", (evt) => {
                if (this.terrain_zoom_value) {
                    this.terrain_zoom_value.innerHTML = this.terrain_zoom.value;
                }
                this.tv.set_terrain_zoom(Number.parseFloat(this.terrain_zoom.value));
            });
            this.terrain_zoom.addEventListener("input", (evt) => {
                if (this.terrain_zoom_value) {
                    this.terrain_zoom_value.innerHTML = this.terrain_zoom.value;
                }
            });
        }

        let intersection_options = {
            "delay": 200 /* check every 200ms */
        };

        const observer = new IntersectionObserver((entries, observer) => {
            this.intersection_callback(entries);
        }, intersection_options);

        // when img elements specify their urls using load_url attributes,
        // observe them and load the images lazily when they come into view
        let images = document.querySelectorAll("img");
        images.forEach((img) => {
            if (img.hasAttribute("load_url")) {
                observer.observe(img);
            }
        });

        // define an ImageFetcher to lazily load the images
        this.image_fetcher = new ImageFetcher(4, (image_id, url) => {
            this.cache_image(image_id, url);
        });

        // cache the data-uris for lazily loaded images
        this.image_url_cache = {};
        this.cached_image_ids = [];
        this.image_url_cache_size = 500;
    }

    /**
     * Provide a standard string representation of dates
     *
     * @param {Date} dt a javascript date
     *
     * @returns {string} in format YYYY-MM-DD
     */
    date_to_string(dt) {
        // return YYY-MM-DD formatted string from Date
        let day = dt.getUTCDate();
        let month = dt.getUTCMonth() + 1;
        let year = dt.getFullYear();
        let s = String(year) + "-" + String(month).padStart(2, '0') + "-" + String(day).padStart(2, '0');
        return s;
    }

    /**
     * Parse a string
     *
     * @param s a string in format YYYY-MM-DD
     *
     * @returns {Date} a javascript Date object parsed from the string
     */
    string_to_date(s) {
        // parse YYYY-MM-DD formatted string to Date
        let day = Number.parseInt(s.slice(8, 10));
        let month = Number.parseInt(s.slice(5, 7));
        let year = Number.parseInt(s.slice(0, 4));
        return new Date(Date.UTC(year, month - 1, day, 12, 0, 0));
    }

    select_grid_date(updated_date) {
        let min_diff = null;
        let min_index = null;
        let updated_dt = this.string_to_date(updated_date);
        for (let idx = 0; idx < this.scenes.index.length; idx++) {
            let item = this.scenes.index[idx];
            let item_dt = this.string_to_date(item.timestamp);
            let diff = Math.abs(item_dt - updated_dt);
            if (min_diff === null || diff < min_diff) {
                min_diff = diff;
                min_index = idx;
            }
        }
        if (min_index !== null) {
            this.select_grid_index(min_index);
        }
    }

    select_grid_index(new_index) {
        let pos = this.scenes.index[new_index].pos;
        let row_id = `row${pos}`;
        let previous_current_page = this.current_page;
        this.current_page = 0;
        while(new_index >= (this.current_page*this.page_size + this.page_size)) {
            this.current_page += 1;
        }
        if (this.current_page !== previous_current_page) {
            this.show_page();
        }
        let row_elt = document.getElementById(row_id);
        if (row_elt) {
            row_elt.scrollIntoView();
        }
    }

    select_overlay_date(updated_date) {
        let min_diff = null;
        let min_index = null;
        let updated_dt = this.string_to_date(updated_date);
        for (let idx = 0; idx < this.index.length; idx++) {
            let item = this.index[idx];
            let item_dt = this.string_to_date(item.timestamp);
            let diff = Math.abs(item_dt - updated_dt);
            if (min_diff === null || diff < min_diff) {
                min_diff = diff;
                min_index = item.pos;
            }
        }
        if (min_index !== null) {
            this.current_index = min_index;
            this.update_time_range();
            this.show().then(() => {});
        }
    }

    prev_page() {
        if (this.current_page > 0) {
            this.current_page -= 1;
            this.show_page();
        }
    }

    next_page() {
        if (this.current_page < this.max_page) {
            this.current_page += 1;
            this.show_page();
        }
    }

    show_page() {
        let page_start = this.current_page * this.page_size;
        let page_end = ((this.current_page+1) * this.page_size)-1;
        for(let idx=0; idx < this.scenes.index.length; idx++) {
            let row = document.getElementById(`row${idx}`);
            if (idx >= page_start && idx <= page_end) {
                row.style.display = 'table-row';
            } else {
                row.style.display = 'none';
            }
        }
        this.page_label.innerText = `(${this.current_page+1}/${this.max_page+1})`;
        this.update_page_range();
    }

    update_page_size() {
        this.page_size = Number.parseInt(this.page_size_control.value);
        this.calculate_max_page();
    }

    update_page_range() {
        if (this.max_page == 0) {
            this.page_range.value = "50";
        } else {
            this.page_range.value = String(100 * (this.current_page / this.max_page));
        }
    }

    calculate_max_page() {
        let nr_scenes = this.scenes.index.length;
        this.max_page = Math.ceil(nr_scenes/this.page_size)-1;
        if (this.current_page > this.max_page) {
            this.current_page = this.max_page;
            this.show_page();
        }
    }

    cache_image(image_id, image_url) {
        this.image_url_cache[image_id] = image_url;
        this.cached_image_ids.push(image_id);
        if (this.cached_image_ids.length > this.image_url_cache_size) {
            delete this.image_url_cache[this.cached_image_ids.splice(0,1)];
        }
    }

    intersection_callback(entries) {
        entries.forEach((entry) => {
            let target = entry.target;
            if (target.hasAttribute("load_url")) {
                if (entry.isIntersecting) {
                    // image is now visible
                    if (target.hasAttribute("load_url")) {
                        let url = target.getAttribute("src");
                        if (url === "") {
                            let img_id = target.id;
                            if (img_id in this.image_url_cache) {
                                target.setAttribute("src",this.image_url_cache[img_id]);
                            } else {
                                this.image_fetcher.submit(img_id);
                            }
                        }
                    }
                } else {
                    // image is no longer visible
                    target.src = "";
                }
            }
        });
    }

    handle_map_mouseover(y_frac, x_frac) {
        let data_content = document.getElementById("data_content");
        if (data_content) {
            let html = "<p>No Data</p>";
            if (this.di && y_frac !== null && x_frac !== null) {
                html = this.di.get_popup_html(y_frac, x_frac)
            }
            data_content.innerHTML = html;
        }
    }

    async load_timeseries() {
        if (this.timeseries_charts === null) {
            this.timeseries_charts = {};
            let r = await fetch("timeseries.json");
            let timeseries = await r.json();
            if (timeseries) {
                timeseries.forEach(o => {
                    let name = o["name"];
                    let csv_url = o["csv_url"];
                    let spec = o["spec"];
                    let div_id = o["div_id"];
                    let chart = new TimeseriesChart(div_id, csv_url, spec);
                    this.timeseries_charts[name] = chart;
                });
            }
        }
    }

    async load() {
        // load data files: scenes.json a
        // this needs to be called before init
        let r = await fetch("scenes.json");
        this.scenes = await r.json();

        if (this.overlay_container) {
            this.lm = new LeafletMap('map', this.scenes.data_height, this.scenes.data_width,
                async (y_frac, x_frac) => {
                    this.handle_map_mouseover(y_frac, x_frac);
                },
                async (zoom) => {
                    this.set_zoom(zoom);
                }
            );

            this.zoom = 1;
            this.handle_map_mouseover(null, null);
        }

        // initially, include all scenes in the index
        this.index = [];
        for (let idx = 0; idx < this.scenes.index.length; idx++) {
            this.scenes.index[idx].original_index = idx + 1;
            this.index.push(this.scenes.index[idx]);
        }

        // set the grid date picker to the date of the first scene
        if (this.scenes.index.length > 0 && this.grid_select_date) {
            this.grid_select_date.value = this.scenes.index[0].timestamp.slice(0,10);
        }

        this.calculate_max_page();
    }

    create_custom_cmap_callback(layer_name, select_control, min_control, max_control) {
        // create a callback to be called when a cmap is changed in the overlay view
        let cb = async (evt) => {
            let new_min = Number.parseFloat(min_control.value);
            let new_max = Number.parseFloat(max_control.value);
            let new_cmap = select_control.value;
            this.data_layers[layer_name] = {"cmap": new_cmap, "vmin": new_min, "vmax": new_max}
            await cmap.load(new_cmap);
            this.update_data_layer(layer_name);
        }
        select_control.addEventListener("change", cb);
        min_control.addEventListener("input", cb);
        max_control.addEventListener("input", cb);
    }

    create_open_callback(index) {
        // create a callback to open a particular scene in the overlay view
        return async (evt) => {
            this.current_index = index;
            this.grid_container.style.display = "none";
            this.overlay_container.style.display = "block";
            this.update_time_range();
            await this.show();
        }
    }

    get_layer_group(layer_name) {
        for(let group in this.scenes.layer_groups) {
            if (this.scenes.layer_groups[group].includes(layer_name)) {
                return group;
            }
        }
        return "";
    }

    async init() {
        // initialise the view, to be called once load has completed
        // bind to the controls in this page


        if (this.grid_view_button) {
            this.grid_view_button.addEventListener("click", (evt) => {
                this.show_container(this.grid_container);
            });
        }

        if (this.grid_view_button2) {
            this.grid_view_button2.addEventListener("click", (evt) => {
                this.show_container(this.grid_container);
            });
        }

        if (this.overlay_view_button) {
            this.overlay_view_button.addEventListener("click", (evt) => {
                this.show_container(this.overlay_container);
            });
        }

        if (this.timeseries_view_button) {
            this.timeseries_view_button.addEventListener("click", async (evt) => {
                this.show_container(null);
                if (this.timeseries_container) {
                    this.timeseries_container.style.display = "block";
                    await this.load_timeseries();
                }
            });
        }

        if (this.next_button) {
            this.next_button.addEventListener("click", async (evt) => {
                if (this.current_index < this.index.length - 1) {
                    this.current_index += 1;
                    this.update_time_range();
                    await this.show();
                }
            });
        }

        if (this.prev_button) {
            this.prev_button.addEventListener("click", async (evt) => {
                if (this.current_index > 0) {
                    this.current_index -= 1;
                    this.update_time_range();
                    await this.show();
                }
            });
        }

        if (this.time_range) {
            this.time_range.addEventListener("change", async (evt) => {
                if (this.index.length) {
                    let fraction = Number.parseFloat(evt.target.value) / 100;
                    this.current_index = Math.round(fraction * (this.index.length - 1));
                    await this.show();
                }
            });
        }

        for (let month = 1; month <= 12; month += 1) {
            let cb_elt = document.getElementById("month" + month);
            if (cb_elt) {
                cb_elt.addEventListener("change", this.create_month_filter_callback(month));
            }
        }

        this.scenes.layers.forEach(layer => {
            let group = this.get_layer_group(layer.name);
            this.layer_opacities[layer.name] = 1;
            if (group && group in this.layer_group_active_layers) {
                // hide layers that are grouped if they are not the first layer in their group
                this.lm.set_layer_opacity(layer.name, 0);
            } else {
                this.lm.set_layer_opacity(layer.name, 1);
                this.layer_group_active_layers[group] = layer.name;
            }
            let r = document.getElementById(layer.name + "_opacity");
            if (r) {
                r.value = "100";
                r.addEventListener("input", this.create_opacity_callback(layer.name));
            }
        });

        if (this.layer_container && this.show_layers) {
            this.show_layers.addEventListener("click", (evt) => {
                this.layer_container.style.display = "block";
            });
        }

        if (this.filter_container && this.show_filters) {
            this.show_filters.addEventListener("click", (evt) => {
                this.filter_container.style.display = "block";
            });
        }

        if (this.info_container && this.show_info) {
            this.show_info.addEventListener("click", (evt) => {
                this.info_container.style.display = "block";
            });
        }

        if (this.data_container && this.show_data) {
            this.show_data.addEventListener("click", (evt) => {
                this.data_container.style.display = "block";
            });
        }

        if (this.close_all_btn) {
            this.close_all_btn.addEventListener("click", (evt) => {
                this.scenes.layers.forEach(layer => {
                    this.layer_opacities[layer.name] = 0.0;
                    this.lm.set_layer_opacity(layer.name, 0.0);
                    let r = document.getElementById(layer.name + "_opacity");
                    r.value = "0";
                });
            });
        }

        const make_hide_column_callback = (col_id) => {
            return (evt) => {
                document.getElementById(col_id).style.visibility = "collapse";
            }
        }

        const make_group_select_column_callback = (layer_name) => {
            return (evt) => {
                this.show_group_column(evt.target.value);
                this.show_group_row(evt.target.value);
            }
        }

        const make_group_select_row_callback = (layer_name) => {
            return (evt) => {
                this.show_group_column(evt.target.value);
                this.show_group_row(evt.target.value);
            }
        }

        this.scenes.layers.forEach(layer => {
            let col_id = layer.name + "_col";
            let hide_btn_id = layer.name + "_hide";
            let hide_btn = document.getElementById(hide_btn_id);
            if (hide_btn) {
                hide_btn.addEventListener("click", make_hide_column_callback(col_id));
                let group_name = this.get_layer_group(layer.name);
                if (group_name) {
                    let group_select_id = layer.name + "_group_select";
                    let group_select = document.getElementById(group_select_id);
                    if (group_select) {
                        group_select.addEventListener("input", make_group_select_column_callback(layer.name));
                    }

                    let group_select_row_id = layer.name + "_group_select_row";
                    let group_select_row = document.getElementById(group_select_row_id);
                    if (group_select_row) {
                        group_select_row.addEventListener("input", make_group_select_row_callback(layer.name));
                    }
                }
            }
        });

        // initialise layer groups to show the first layer
        let groups_initialised = {};
        this.scenes.layers.forEach(layer => {
            let group_name = this.get_layer_group(layer.name);
            if (group_name) {
                if (!(group_name in groups_initialised)) {
                    this.show_group_row(layer.name);
                    this.show_group_column(layer.name);
                    groups_initialised[layer.name] = true;
                }
            }
        });

        for (let i = 0; i < this.scenes.index.length; i++) {
            let open_btn_id = "open_" + i + "_btn";
            let btn = document.getElementById(open_btn_id);
            btn.addEventListener("click", this.create_open_callback(i));
        }

        for (let layer_idx in this.scenes.layers) {
            let layer = this.scenes.layers[layer_idx];
            if (layer.has_data) {
                let min_control = document.getElementById(layer.name + "_min_input");
                let max_control = document.getElementById(layer.name + "_max_input");
                let select_control = document.getElementById(layer.name + "_camp_selector");
                if (min_control && max_control && select_control) {
                    this.create_custom_cmap_callback(layer.name, select_control, min_control, max_control);
                }
            }
        }

        if (this.terrain_view_button) {
            this.terrain_view_button.addEventListener("click", async () => {
                await this.open_terrain_view();
            });
        }

        if (this.exit_terrain_view_button) {
            this.exit_terrain_view_button.addEventListener("click", () => {
                this.close_terrain_view();
            });
        }

        this.update_filters();

        // by default open the grid container if it exists
        if (this.grid_container) {
            const params = new URLSearchParams(window.location.search);
            if (params.has('index')) {
                this.current_index = Number.parseInt(params.get('index'))-1;
                if (this.current_index < 0) {
                    this.current_index = 0;
                }
                if (this.current_index >= this.index.length) {
                    this.current_index = this.index.length-1;
                }
                this.show_container(this.overlay_container);
            } else {
                this.show_container(this.grid_container);
                this.show_page();
            }
        } else if (this.timeseries_container) {
            // otherwise open the timeseries container
            this.show_container(this.timeseries_container);
        }

        if (this.time_range) {
            this.update_time_range();
        }

        if (this.grid_select_date) {
            this.grid_select_date.addEventListener("input", (evt) => {
               this.select_grid_date(this.grid_select_date.value);
            });
        }

        if (this.overlay_select_date) {
            this.overlay_select_date.addEventListener("input", (evt) => {
               this.select_overlay_date(this.overlay_select_date.value);
            });
        }

        this.prev_page_btn.addEventListener("click", (ev) => {
            this.prev_page();
        });

        this.next_page_btn.addEventListener("click", (ev) => {
            this.next_page();
        });

        this.page_size_control.addEventListener("input", (evt) => {
            this.update_page_size();
            this.show_page();
        });

        this.page_range.addEventListener("input", (evt) => {
             if (this.max_page > 0) {
                 let frac = Number.parseFloat(this.page_range.value) / 100;
                 this.current_page = Math.round(frac * this.max_page);
                 this.show_page();
             }
        });

        this.update_page_size();
        this.show_page();

        await this.show();
    }

    show_group_column(layer_name) {
        let group_name = this.get_layer_group(layer_name);
        if (group_name) {
            let grouped_layers = this.scenes.layer_groups[group_name];
            for (let idx = 0; idx < grouped_layers.length; idx += 1) {
                let grouped_layer_name = grouped_layers[idx];
                let col_id = grouped_layer_name + "_col";
                if (grouped_layer_name === layer_name) {
                    document.getElementById(col_id).style.visibility = "visible";
                } else {
                    document.getElementById(col_id).style.visibility = "collapse";
                }
                let group_select_id = grouped_layer_name + "_group_select";
                document.getElementById(group_select_id).value = layer_name;
            }
        }
    }

    show_group_row(layer_name) {
        let group_name = this.get_layer_group(layer_name);
        if (group_name) {
            let grouped_layers = this.scenes.layer_groups[group_name];
            for (let idx=0; idx<grouped_layers.length; idx+=1) {
                let grouped_layer_name = grouped_layers[idx];
                let group_select_row_id = layer_name + "_group_select_row";
                let overlay_row_id = grouped_layer_name + "_overlay_row";
                if (grouped_layer_name === layer_name) {
                    document.getElementById(overlay_row_id).style.display = "table-row";
                    this.lm.set_layer_opacity(layer_name, this.layer_opacities[layer_name]);
                } else {
                    document.getElementById(overlay_row_id).style.display = "none";

                    this.lm.set_layer_opacity(grouped_layer_name, 0);
                }
                document.getElementById(group_select_row_id).value = layer_name;
            }
            this.layer_group_active_layers[group_name] = layer_name;
        }
    }

    show_container(target_container) {
        let containers = [this.grid_container, this.timeseries_container, this.overlay_container, this.terrain_container];
        containers.forEach(container => {
            if (container && container !== target_container) {
                container.style.display = "none";
            }
        });
        containers.forEach(container => {
            if (container && container === target_container) {
                container.style.display = "block";
            }
        });
    }

    set_zoom(zoom) {
        // update the overlay zoom
        this.zoom = zoom;
        this.scenes.layers.forEach(layer => {
            if (layer.wms_url) {
                let wms_url = layer.wms_url.replace("{WIDTH}", "" + this.zoom * image_width).replace("{HEIGHT}", "" + this.zoom * image_width)
                    .replace("{XMIN}", "" + this.scenes.index[this.current_index].x_min)
                    .replace("{YMIN}", "" + this.scenes.index[this.current_index].y_min)
                    .replace("{XMAX}", "" + this.scenes.index[this.current_index].x_max)
                    .replace("{YMAX}", "" + this.scenes.index[this.current_index].y_max);
                this.lm.add_image_layer(layer.name, wms_url);
            }
        });
    }

    update_time_range() {
        // called from the overlay view on initialisation or after filters are updated or after the current index is updated
        // update the time range slider to reflect the current index
        if (this.index.length) {
            this.time_range.value = String(100 * (this.current_index / (this.index.length - 1)));
        } else {
            this.time_range.value = "50";
        }
    }

    update_filters() {
        // called from the overlay view after filters are updated
        // rebuild the main index based on the new filter settings
        this.current_index = 0;
        this.index = [];
        for (let idx = 0; idx < this.scenes.index.length; idx++) {
            let item = this.scenes.index[idx];
            let month = Number.parseInt(item.timestamp.slice(5, 7));
            if (!(month in this.months_excluded)) {
                this.index.push(item);
            }
        }
    }

    create_month_filter_callback(month) {
        // create a callback for when a month filter checkbox is checked/unchecked
        return async (evt) => {
            if (!evt.target.checked) {
                this.months_excluded[month] = true;
            } else {
                delete this.months_excluded[month];
            }
            this.update_filters();
            this.update_time_range();
            await this.show();
        }
    }

    create_opacity_callback(layer_name) {
        // create a callback for changes to an overlay view opacity slider
        return (evt) => {
            let opacity = Number.parseFloat(evt.target.value) / 100;
            this.layer_opacities[layer_name] = opacity;
            this.lm.set_layer_opacity(layer_name, opacity);
            let group_name = this.get_layer_group(layer_name);
            if (group_name) {
                // this layer belongs to a group
                // apply the same opacity to all layers in the same group
                let grouped_layers = this.scenes.layer_groups[group_name];
                grouped_layers.forEach((group_layer_name) => {
                    if (layer_name !== group_layer_name) {
                        this.layer_opacities[group_layer_name] = opacity;
                        this.lm.set_layer_opacity(layer_name, opacity);
                        let r = document.getElementById(group_layer_name + "_opacity");
                        if (r) {
                            r.value = evt.target.value;
                        }
                    }
                });
            }
        }
    }

    populate_info(info_content, info) {
        // populate a table with scene information, in the overlay view
        let tbl = document.createElement("table");
        for (let key in info) {
            let tr = document.createElement("tr");
            let tc0 = document.createElement("td");
            let tc1 = document.createElement("td");
            tc0.innerHTML = key;
            tc1.innerHTML = info[key];
            tr.appendChild(tc0);
            tr.appendChild(tc1);
            tbl.appendChild(tr);
        }
        info_content.innerHTML = "";
        info_content.appendChild(tbl);
    }

    update_data_layer(layer_name) {
        let dl = this.data_layers[layer_name];
        let lurl = this.di.get_legend_url(dl.cmap, dl.vmin, dl.vmax, 20, 200);
        let img_id = layer_name + "_legend_img";
        document.getElementById(img_id).src = lurl;
        this.update_image(layer_name);
    }

    update_image(layer_name) {
        let image_srcs = this.index[this.current_index].image_srcs;
        let url = "";
        if (layer_name in this.data_layers) {
            let dl = this.data_layers[layer_name];
            url = this.di.get_image_url(layer_name, dl.cmap, dl.vmin, dl.vmax);
        } else {
            url = image_srcs[layer_name];
        }
        this.lm.add_image_layer(layer_name, url);
        return url;
    }

    open_spinner() {
        if (!this.spinner) {
            this.spinner = document.createElement("div");
            this.spinner.setAttribute("class", "spinner");
            this.root_element.appendChild(this.spinner);
        }
    }

    close_spinner() {
        if (this.spinner) {
            this.root_element.removeChild(this.spinner);
        }
        this.spinner = null;
    }

    async show() {

        if (this.time_range) {
            this.time_range.disabled = true;
        }
        if (this.next_button) {
            this.next_button.disabled = true;
        }
        if (this.prev_button) {
            this.prev_button.disabled = true;
        }

        this.open_spinner();

        // called in the overlay view to show the currently selected scene

        if (this.index.length == 0) {
            // nothing to show, hide the imagery
            if (this.lm) {
                this.lm.clear_layers();
            }
            if (this.scene_label_elt) {
                let overlay_label = "0/0";
                this.scene_label_elt.innerHTML = overlay_label;
            }
            if (this.terrain_view_button) {
                this.terrain_view_button.disabled = true;
            }
            this.close_spinner();
            return;
        } else {
            if (this.terrain_view_button) {
                this.terrain_view_button.disabled = false;
            }
        }

        this.di = new DataImage("viridis");
        let data_srcs = this.index[this.current_index].data_srcs;
        for (let layer_name in data_srcs) {
            this.di.register_layer(layer_name);
            await this.di.load(layer_name, data_srcs[layer_name]);
        }

        this.overlay_urls = {};

        let label_specs = this.index[this.current_index].label_specs;

        for (let idx = this.scenes.layers.length - 1; idx >= 0; idx = idx - 1) {
            let layer_name = this.scenes.layers[idx].name;
            let image_url = this.update_image(layer_name);
            this.overlay_urls[layer_name] = image_url;
        }


        if (this.info_content) {
            let info = this.index[this.current_index].info;
            this.populate_info(this.info_content, info);
        }

        if (this.scene_label_elt) {
            let overlay_label = "0/0";
            if (this.index.length) {
                overlay_label = "(" + (this.current_index + 1) + "/" + this.index.length + ") ";
            }
            if (this.overlay_select_date) {
                 this.overlay_select_date.value = this.index[this.current_index].timestamp.slice(0,10);
            }
            this.scene_label_elt.innerHTML = overlay_label;
        }

        this.time_range.disabled = false;
        this.next_button.disabled = false;
        this.prev_button.disabled = false;

        this.close_spinner();
    }

    async get_overlay_combined_image() {
        let image_urls = [];
        for (let idx = this.scenes.layers.length - 1; idx >= 0; idx = idx - 1) {
            let layer_name = this.scenes.layers[idx].name;
            let image_url = this.overlay_urls[layer_name];
            let group = this.get_layer_group(layer_name);
            if (group && this.layer_group_active_layers[group] !== layer_name) {
                continue;
            }
            let opacity = this.layer_opacities[layer_name];
            image_urls.push([image_url,opacity]);
        }

        function make_image_fetcher(url) {
            return new Promise(resolve => {
                let img = new Image();
                img.onload = () => {
                    resolve(img);
                }
                img.src = url;
            });
        }

        let cnv = new OffscreenCanvas(this.di.get_width(), this.di.get_height());
        let ctx = cnv.getContext("2d");
        for(let idx=0; idx<image_urls.length; idx++) {
            let url = image_urls[idx][0]
            let opacity = image_urls[idx][1];
            let p = make_image_fetcher(url);
            let img = await p;
            ctx.globalAlpha = opacity;
            ctx.drawImage(img, 0, 0);
            ctx.globalAlpha = 1.0;
        }
        let blob = await cnv.convertToBlob({"type":"image/png"});
        return URL.createObjectURL(blob);
    }

    setup_drag(elt, header_elt, initial_top, initial_left) {
        // set up draggable behaviour on an element
        var startx, starty, dx, dy;

        elt.style.top = initial_top + "px";
        elt.style.left = initial_left + "px";

        var top = initial_top;
        var left = initial_left;

        header_elt.onmousedown = start_drag;

        function start_drag(e) {
            e.preventDefault();
            startx = e.clientX;
            starty = e.clientY;
            document.onmouseup = close_drag;
            document.onmousemove = move_drag;
        }

        function move_drag(e) {
            e.preventDefault();

            dx = startx - e.clientX;
            dy = starty - e.clientY;
            startx = e.clientX;
            starty = e.clientY;

            top = top - dy;
            left = left - dx;

            elt.style.top = top + "px";
            elt.style.left = left + "px";
        }

        function close_drag() {
            document.onmouseup = null;
            document.onmousemove = null;
        }
    }

    async open_terrain_view() {
        this.show_container(this.terrain_container);
        let elevation_band = this.scenes["terrain_view"]["elevation_band"];
        let image_url = await this.get_overlay_combined_image();
        let zoom = 1;
        if (this.terrain_zoom) {
            zoom = Number.parseFloat(this.terrain_zoom.value);
        }
        this.tv = new TerrainView(this.di, elevation_band, image_url, zoom);
        this.tv.open();
    }

    close_terrain_view() {
        this.tv.close();
        this.tv = null;
        this.show_container(this.overlay_container);
    }
}

window.addEventListener("load", async (ect) => {
    let hv = new HtmlView();
    await hv.load();
    hv.init();
    let layer_container = document.getElementById("layer_container");
    if (layer_container) {
        hv.setup_drag(layer_container, document.getElementById("layer_container_header"), 400, 400);
        document.getElementById("close_layer_btn").addEventListener("click", (evt) => {
           layer_container.style.display = "none";
        });
    }

    let filter_container = document.getElementById("filter_container");
    if (filter_container) {
        hv.setup_drag(filter_container, document.getElementById("filter_container_header"), 100, 400);
        document.getElementById("close_filter_btn").addEventListener("click", (evt) => {
           filter_container.style.display = "none";
        });
        filter_container.style.display = "none";
    }

    let info_container = document.getElementById("info_container");
    if (info_container) {
        hv.setup_drag(info_container, document.getElementById("info_container_header"), 200, 400);
        document.getElementById("close_info_btn").addEventListener("click", (evt) => {
           info_container.style.display = "none";
        });
        info_container.style.display = "none";
    }

    let data_container = document.getElementById("data_container");
    if (data_container) {
        hv.setup_drag(data_container, document.getElementById("data_container_header"), 400, 400);
        document.getElementById("close_data_btn").addEventListener("click", (evt) => {
           data_container.style.display = "none";
        });
        data_container.style.display = "none";
    }
});
