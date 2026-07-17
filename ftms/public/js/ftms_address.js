function load_leaflet(callback) {
    if (window.L && document.querySelector('#leaflet-css') && window.L.Control.Geocoder) { callback(); return; }
    if (!document.querySelector('#leaflet-css')) {
        var el = document.createElement('link'); el.id = 'leaflet-css'; el.rel = 'stylesheet';
        el.href = '/assets/ftms/leaflet/css/leaflet.css'; document.head.appendChild(el);
    }
    if (!document.querySelector('#leaflet-geocoder-css')) {
        var el = document.createElement('link'); el.id = 'leaflet-geocoder-css'; el.rel = 'stylesheet';
        el.href = '/assets/ftms/leaflet/plugins/Control.Geocoder.css'; document.head.appendChild(el);
    }
    if (!document.querySelector('#leaflet-fullscreen-css')) {
        var el = document.createElement('link'); el.id = 'leaflet-fullscreen-css'; el.rel = 'stylesheet';
        el.href = '/assets/ftms/leaflet/plugins/Control.FullScreen.css'; document.head.appendChild(el);
    }
    if (window.L && window.L.Control.Geocoder) { callback(); return; }
    var scripts = ['/assets/ftms/leaflet/js/leaflet.js', '/assets/ftms/leaflet/plugins/Control.FullScreen.js', '/assets/ftms/leaflet/plugins/Control.Geocoder.js'];
    function next() { if (!scripts.length) { callback(); return; } var s = document.createElement('script'); s.src = scripts.shift(); s.onload = next; document.head.appendChild(s); }
    next();
}

var addr_timeout = null;

function get_context(frm) {
    var p = [];
    if (frm.doc.city) p.push(frm.doc.city);
    if (frm.doc.state) p.push(frm.doc.state);
    if (frm.doc.country) p.push(frm.doc.country);
    return p.join(', ');
}

function setup_autocomplete(frm) {
    var field = frm.fields_dict.address_line_1;
    if (!field || field.__ac) return;
    field.__ac = true;
    var inp = field.$input ? field.$input[0] : null;
    if (!inp) return;
    inp.addEventListener('input', function() {
        clearTimeout(addr_timeout);
        if (this.value.length < 3) return;
        addr_timeout = setTimeout(function() {
            var ctx = get_context(frm);
            var q = this.value + (ctx ? ', ' + ctx : '');
            var x = new XMLHttpRequest();
            x.open('GET', 'https://nominatim.openstreetmap.org/search?format=json&limit=5&q=' + encodeURIComponent(q));
            x.onload = function() { if (x.status === 200) show_suggestions(frm, inp, JSON.parse(x.responseText)); };
            x.send();
        }.bind(this), 400);
    });
    inp.addEventListener('blur', function() {
        setTimeout(function() { hide_suggestions(); }, 200);
        setTimeout(function() { if (!frm.doc.latitude) split_addr(frm); }, 500);
    });
}

function show_suggestions(frm, inp, results) {
    var old = document.getElementById('addr-suggest');
    if (old) old.remove();
    if (!results || !results.length) return;
    var r = inp.getBoundingClientRect();
    var d = document.createElement('div');
    d.id = 'addr-suggest';
    d.style.cssText = 'position:fixed;z-index:9999;background:#fff;border:1px solid #d1d8dd;border-radius:4px;max-height:200px;overflow-y:auto;width:' + r.width + 'px;box-shadow:0 6px 12px rgba(0,0,0,0.15);font-size:12px;';
    results.forEach(function(res) {
        var item = document.createElement('div');
        item.textContent = res.display_name;
        item.style.cssText = 'padding:8px 12px;cursor:pointer;border-bottom:1px solid #f0f0f0;';
        item.onmouseover = function() { this.style.background = '#f5f5f5'; };
        item.onmouseout = function() { this.style.background = '#fff'; };
        item.onmousedown = function(e) { e.preventDefault(); select_result(frm, res); };
        d.appendChild(item);
    });
    d.style.left = r.left + 'px';
    d.style.top = (r.bottom + 4) + 'px';
    document.body.appendChild(d);
}

function hide_suggestions() {
    var old = document.getElementById('addr-suggest');
    if (old) old.remove();
}

function select_result(frm, result) {
    hide_suggestions();
    frm.set_value('address_line_1', result.display_name.split(',')[0].trim());
    fill_from(frm, result);
}

function split_addr(frm) {
    var addr = frm.doc.address_line_1;
    if (!addr || addr.length < 5 || frm.doc.latitude) return;
    var ctx = get_context(frm);
    var q = addr + (ctx ? ', ' + ctx : '');
    var x = new XMLHttpRequest();
    x.open('GET', 'https://nominatim.openstreetmap.org/search?format=json&limit=1&q=' + encodeURIComponent(q));
    x.onload = function() {
        if (x.status !== 200) return;
        var r = JSON.parse(x.responseText);
        if (r && r.length) fill_from(frm, r[0]);
    };
    x.send();
}

function fill_from(frm, result) {
    frm.set_value('latitude', parseFloat(result.lat));
    frm.set_value('longitude', parseFloat(result.lon));
    var a = result.address || {};
    frm.set_value('address_line_1', result.display_name.split(',')[0].trim());
    if (result.name && result.name !== result.display_name.split(',')[0].trim()) {
        frm.set_value('address_line_2', result.name);
    }
    frm.set_value('city', a.city || a.town || a.village || a.county || '');
    frm.set_value('state', a.state || '');
    frm.set_value('country', a.country || '');
    frm.set_value('zip_code', a.postcode || '');
    frm.set_value('subdivision', a.suburb || a.neighbourhood || a.city_district || '');
    update_pin(frm);
}

function init_map(frm) {
    var field = frm.fields_dict.map_view;
    if (!field) return;
    load_leaflet(function() {
        if (frm.__map) { frm.__map.invalidateSize(); return; }
        field.$wrapper.html('<div class="leaflet-map" style="height:350px;border:1px solid #d1d8dd;border-radius:8px;"></div>');
        var lat = parseFloat(frm.doc.latitude) || 51.505;
        var lon = parseFloat(frm.doc.longitude) || -0.09;
        frm.__map = L.map(field.$wrapper.find('.leaflet-map')[0], {fullscreenControl: true}).setView([lat, lon], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution: '&copy; OSM'}).addTo(frm.__map);
        L.control.scale({imperial: false}).addTo(frm.__map);
        frm.__pin = L.marker([lat, lon], {draggable: true}).addTo(frm.__map);
        frm.__pin.on('dragend', function() {
            var p = frm.__pin.getLatLng();
            frm.set_value('latitude', p.lat); frm.set_value('longitude', p.lng);
            reverse_geo(frm, p.lat, p.lng);
        });
        frm.__map.on('click', function(e) {
            var p = e.latlng;
            if (frm.__pin) frm.__pin.setLatLng(p); else frm.__pin = L.marker(p, {draggable: true}).addTo(frm.__map);
            frm.set_value('latitude', p.lat); frm.set_value('longitude', p.lng);
            reverse_geo(frm, p.lat, p.lng);
        });
        if (window.L.Control.Geocoder) {
            L.Control.geocoder({defaultMarkGeocode: false, placeholder: 'Search map...'}).on('markgeocode', function(e) {
                var g = e.geocode, c = g.center;
                frm.__map.setView(c, 15);
                if (frm.__pin) frm.__pin.setLatLng(c); else frm.__pin = L.marker(c, {draggable: true}).addTo(frm.__map);
                fill_from(frm, {lat: c.lat, lon: c.lng, display_name: g.name, address: g.properties || {}, name: g.name.split(',')[0]});
            }).addTo(frm.__map);
        }
        setTimeout(function() { frm.__map.invalidateSize(); }, 300);
    });
}

function update_pin(frm) {
    var lat = parseFloat(frm.doc.latitude), lon = parseFloat(frm.doc.longitude);
    if (!lat || !lon) return;
    if (frm.__map && frm.__pin) { frm.__pin.setLatLng([lat, lon]); frm.__map.setView([lat, lon], frm.__map.getZoom()); }
}

function reverse_geo(frm, lat, lon) {
    var x = new XMLHttpRequest();
    x.open('GET', 'https://nominatim.openstreetmap.org/reverse?format=json&lat=' + lat + '&lon=' + lon);
    x.onload = function() {
        if (x.status !== 200) return;
        var r = JSON.parse(x.responseText);
        if (!r || !r.address) return;
        frm.set_value('address_line_1', r.display_name.split(',')[0].trim());
        if (r.name && r.name !== r.display_name.split(',')[0].trim()) frm.set_value('address_line_2', r.name);
        var a = r.address;
        frm.set_value('city', a.city || a.town || a.village || a.county || '');
        frm.set_value('state', a.state || ''); frm.set_value('country', a.country || '');
        frm.set_value('zip_code', a.postcode || '');
        frm.set_value('subdivision', a.suburb || a.neighbourhood || a.city_district || '');
    };
    x.send();
}

// Hook into Address form
frappe.ui.form.on("Address", {
    refresh: function(frm) {
        init_map(frm);
        setup_autocomplete(frm);
    },
    latitude: function(frm) { update_pin(frm); },
    longitude: function(frm) { update_pin(frm); },
    country: function(frm) {
        toggle_zatca(frm);
        var field = frm.fields_dict.address_line_1;
        if (field && field.$input) {
            field.$input.dispatchEvent(new Event('input'));
        }
    },
});
