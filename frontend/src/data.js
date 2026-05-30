// Load committed static datasets from the app's public/data folder.
//
// The deployed app is static (GitHub Pages), so widgets read pre-compiled JSON
// snapshots instead of calling a backend. import.meta.env.BASE_URL makes this
// work both at the site root (dev) and under the /vibe-economics/ subpath (Pages).
const cache = new Map();

export async function loadDataset(name) {
  if (cache.has(name)) return cache.get(name);
  const url = `${import.meta.env.BASE_URL}data/${name}.json`;
  const promise = fetch(url).then((res) => {
    if (!res.ok) throw new Error(`Failed to load dataset ${name}: ${res.status}`);
    return res.json();
  });
  cache.set(name, promise);
  return promise;
}
