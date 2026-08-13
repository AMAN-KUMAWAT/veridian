import React, { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";

const color = (s) => (s >= 60 ? "#EF4444" : s >= 40 ? "#F59E0B" : "#22C55E");

export const PortfolioMap = ({ points = [] }) => {
  const elRef = useRef(null);
  const mapRef = useRef(null);
  const clusterRef = useRef(null);

  useEffect(() => {
    if (!elRef.current || mapRef.current) return;
    const map = L.map(elRef.current, { scrollWheelZoom: false }).setView([39.5, -98.35], 3);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      attribution: "&copy; OpenStreetMap contributors &copy; CARTO", maxZoom: 19,
    }).addTo(map);
    clusterRef.current = L.markerClusterGroup({
      chunkedLoading: true, maxClusterRadius: 55, spiderfyOnMaxZoom: true, showCoverageOnHover: false,
    });
    map.addLayer(clusterRef.current);
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => {
    const map = mapRef.current, cluster = clusterRef.current;
    if (!map || !cluster) return;
    cluster.clearLayers();
    const latlngs = [];
    points.forEach((p) => {
      const m = L.circleMarker([p.lat, p.lon], {
        radius: 7, color: "#ffffff", weight: 1.5, fillColor: color(p.composite), fillOpacity: 0.9,
      }).bindPopup(
        `<b>${p.policy_id}</b> &middot; ${p.submitter_name || ""}<br>${p.address}<br>` +
        `Composite: <b style="color:${color(p.composite)}">${p.composite}</b> &middot; $${Number(p.sum_insured).toLocaleString()}`
      );
      cluster.addLayer(m);
      latlngs.push([p.lat, p.lon]);
    });
    if (latlngs.length) { try { map.fitBounds(latlngs, { padding: [40, 40], maxZoom: 8 }); } catch (e) {} }
    setTimeout(() => map.invalidateSize(), 250);
  }, [points]);

  return <div ref={elRef} data-testid="portfolio-map" style={{ height: 380, width: "100%", borderRadius: 10, zIndex: 0 }} />;
};
