"""
Test Topological Engine on Goa, Mangaluru, and Mumbai Road Networks.
"""
import json
from pathlib import Path
import networkx as nx
import math

def haversine(coord1, coord2):
    lon1, lat1 = coord1
    lon2, lat2 = coord2
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 3)

def test_district_graph(district_id: str):
    p = Path(f"data/geo/roads/{district_id}.geojson")
    if not p.exists():
        print(f"File not found: {p}")
        return
    data = json.loads(p.read_text(encoding="utf-8"))
    features = data.get("features", [])
    print(f"\n==================== {district_id.upper()} ROAD NETWORK ====================")
    print(f"Features: {len(features)}")

    G = nx.Graph()
    for f in features:
        props = f["properties"]
        geom = f["geometry"]
        coords = geom["coordinates"]
        rid = props["id"]
        elev = props.get("elevation_m", 2.0)
        u = (round(coords[0][0], 4), round(coords[0][1], 4))
        v = (round(coords[-1][0], 4), round(coords[-1][1], 4))
        dist_km = sum(haversine(coords[i], coords[i+1]) for i in range(len(coords)-1))
        G.add_edge(u, v, id=rid, name=props["name"], elevation_m=elev, length_km=dist_km, properties=props, coordinates=coords)

    print(f"Graph Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")
    print("Connected Components:", nx.number_connected_components(G))

    # Test edge betweenness centrality
    ebc = nx.edge_betweenness_centrality(G)
    top_edges = sorted(ebc.items(), key=lambda x: x[1], reverse=True)[:3]
    print("\nTop Centrality Bottlenecks (Cut-edges / Vital Links):")
    for (u, v), score in top_edges:
        edge_data = G[u][v]
        print(f"  * {edge_data['name']} (id={edge_data['id']}): Centrality = {score:.3f}, Elev = {edge_data['elevation_m']}m")

    # Bridges (cut-edges)
    bridges = list(nx.bridges(G))
    print(f"\nTopological Bridges (Edges whose severance disconnects the network): {len(bridges)}")
    for u, v in bridges[:5]:
        print(f"  * {G[u][v]['name']} ({G[u][v]['id']})")

if __name__ == "__main__":
    for d in ["goa", "mangaluru", "mumbai"]:
        test_district_graph(d)
