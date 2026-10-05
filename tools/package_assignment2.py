"""Bundle immutable network inputs; students only need ZIP + O-D CSV."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json

from tools.prepare_assignment2 import sha256

SOURCE = Path('outputs/assignment2_source')
DESTINATION = Path('assignment/data')


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    names = ['road_graph_nodes.parquet','road_graph_edges.parquet','songpa.geojson']
    names += [str(p.relative_to(SOURCE)).replace('\\','/') for p in sorted((SOURCE/'gtfs').glob('*.parquet'))]
    manifest = json.loads((SOURCE/'manifest.json').read_text('utf-8'))
    manifest['files'] = {name: {'bytes':(SOURCE/name).stat().st_size,'sha256':sha256(SOURCE/name)} for name in names}
    manifest.pop('synthetic_od', None)
    with ZipFile(DESTINATION/'songpa_network.zip','w',compression=ZIP_DEFLATED) as z:
        for name in names:
            z.write(SOURCE/name, name)
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    if (SOURCE/'od.csv').exists():
        (DESTINATION/'od.csv').write_bytes((SOURCE/'od.csv').read_bytes())
    print('Packaged network:', DESTINATION/'songpa_network.zip')


if __name__ == '__main__':
    main()
