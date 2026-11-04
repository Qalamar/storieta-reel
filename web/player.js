const $ = (id) => document.getElementById(id);
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
let current = -1, mode = 'scene', flat = false, gallery = false, paused = reduced.matches;
let scenes = [], cards = [], observer;
const hidden = new Map();
function asset(path, base) {
  const url = new URL(path, base);
  if (!['http:', 'https:'].includes(url.protocol) || url.origin !== location.origin) throw new Error('Use assets served from this site.');
  return url.href;
}
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}
function picture(src, className, parent, alt = '') {
  const img = el('img', className); img.src = src; img.alt = alt; img.draggable = false; parent.append(img); return img;
}
function refresh() {
  document.body.classList.toggle('paused', paused);
  $('motion').disabled = reduced.matches;
  $('motion').textContent = reduced.matches ? 'Reduced motion' : paused ? 'Play motion' : 'Pause motion';
  $('motion').setAttribute('aria-pressed', String(!paused));
  $('flat').setAttribute('aria-pressed', String(flat));
  $('flat').textContent = flat ? 'Return to layers' : 'Compare original';
  document.querySelectorAll('[data-mode]').forEach(node => {
    if (node.tagName === 'BUTTON') node.setAttribute('aria-pressed', String(node.dataset.mode === mode));
    else node.dataset.mode = mode;
  });
  cards.forEach((card, index) => {
    card.querySelector('.art').classList.toggle('flat', flat);
    card.querySelectorAll('.figure').forEach((node, layer) => node.classList.toggle('off', Boolean(hidden.get(index)?.has(layer))));
  });
}
function activate(index) {
  if (current === index) return;
  current = index;
  const scene = scenes[index];
  $('title').textContent = scene.title || 'Untitled scene';
  $('book').textContent = scene.book || '';
  $('caption').textContent = scene.caption || 'Explore the characters and background as separate layers.';
  $('reading').hidden = !scene.sentence;
  $('reading').textContent = scene.sentence ? `Selected moment: “${scene.sentence}”` : '';
  $('counter').textContent = `Scene ${index + 1} / ${scenes.length}`;
  $('position').textContent = `${index + 1} of ${scenes.length}`;
  $('previous').disabled = index === 0;
  $('next').disabled = index === scenes.length - 1;
  $('cast').replaceChildren();
  scene.layers.forEach((layer, layerIndex) => {
    const label = el('label');
    const input = document.createElement('input'); input.type = 'checkbox';
    input.checked = !hidden.get(index)?.has(layerIndex);
    input.addEventListener('change', () => {
      if (!hidden.has(index)) hidden.set(index, new Set());
      if (input.checked) hidden.get(index).delete(layerIndex); else hidden.get(index).add(layerIndex);
      refresh();
    });
    label.append(input, document.createTextNode(layer.name || `Figure ${layerIndex + 1}`));
    $('cast').append(label);
  });
  if (!scene.layers.length) $('cast').textContent = 'No separated characters in this scene.';
}
function go(index, smooth = true) {
  index = Math.max(0, Math.min(scenes.length - 1, index));
  if (index < 0) return;
  activate(index);
  $('scenes').scrollTo({top: cards[index].offsetTop - cards[0].offsetTop, behavior: smooth && !reduced.matches ? 'smooth' : 'instant'});
}
function setGallery(value) {
  gallery = value;
  document.body.classList.toggle('gallery', value);
  $('gallery').setAttribute('aria-pressed', String(value));
  $('gallery').textContent = value ? 'Back to reel' : 'Scene wall';
  cards.forEach(card => { card.tabIndex = value ? 0 : -1; card.setAttribute('role', value ? 'button' : 'region'); });
  requestAnimationFrame(() => value ? $('scenes').scrollTo(0, 0) : go(current, false));
}
$('previous').onclick = () => go(current - 1);
$('next').onclick = () => go(current + 1);
$('gallery').onclick = () => setGallery(!gallery);
$('flat').onclick = () => { flat = !flat; refresh(); };
$('motion').onclick = () => { paused = !paused; refresh(); };
$('depth').oninput = (event) => {
  document.documentElement.style.setProperty('--depth', Number(event.target.value) / 100);
  $('depth-value').textContent = `${event.target.value}%`;
};
document.querySelectorAll('button[data-mode]').forEach(button => button.onclick = () => { mode = button.dataset.mode; flat = false; refresh(); });
$('scenes').addEventListener('keydown', event => {
  if (event.target !== $('scenes')) return;
  if (['ArrowDown', 'ArrowRight', 'ArrowUp', 'ArrowLeft'].includes(event.key)) {
    event.preventDefault(); go(current + (['ArrowDown', 'ArrowRight'].includes(event.key) ? 1 : -1));
  }
});
reduced.addEventListener('change', () => { paused = reduced.matches; refresh(); });
try {
  const manifestURL = asset(new URLSearchParams(location.search).get('manifest') || 'sample/reel.json', location.href);
  const response = await fetch(manifestURL);
  if (!response.ok) throw new Error('Reel manifest was not found.');
  const manifest = await response.json();
  if (manifest.version !== 1 || !Array.isArray(manifest.scenes) || !manifest.scenes.length) throw new Error('No playable scenes in this manifest.');
  $('provenance').textContent = manifest.provenance || '';
  scenes = manifest.scenes;
  scenes.forEach((scene, index) => {
    if (!(scene.width > 0 && scene.height > 0) || !scene.image || !scene.background || !Array.isArray(scene.layers)) throw new Error('A scene is missing dimensions or image layers.');
    const card = el('section', 'scene-card'); card.setAttribute('aria-label', scene.title || `Scene ${index + 1}`);
    const art = el('div', 'art'); art.dataset.mode = mode; art.style.setProperty('--ratio', scene.width / scene.height);
    picture(asset(scene.background, manifestURL), 'base', art, scene.title || 'Scene background');
    scene.layers.forEach((layer, i) => {
      const img = picture(asset(layer.src, manifestURL), 'figure', art, layer.name || 'Character');
      img.style.setProperty('--level', scene.layers.length - i); img.style.zIndex = scene.layers.length - i;
    });
    picture(asset(scene.image, manifestURL), 'original', art);
    const caption = el('p', 'scene-label', scene.title || `Scene ${index + 1}`);
    card.append(art, caption); cards.push(card); $('scenes').append(card);
    card.addEventListener('click', () => { if (gallery) { activate(index); setGallery(false); } });
    card.addEventListener('keydown', event => {
      if (gallery && ['Enter', ' '].includes(event.key)) { event.preventDefault(); activate(index); setGallery(false); }
    });
  });
  await Promise.all([...$('scenes').querySelectorAll('img')].map(img => img.decode()));
  activate(0); refresh();
  observer = new IntersectionObserver(entries => {
    if (gallery) return;
    for (const entry of entries) if (entry.intersectionRatio > .6) activate(cards.indexOf(entry.target));
  }, {root: $('scenes'), threshold: [.6]});
  cards.forEach(card => observer.observe(card));
  document.body.dataset.ready = 'true';
} catch (error) {
  $('status').textContent = `${error.message} Start the server from the repository root and check the manifest path and its image files.`;
  $('counter').textContent = 'Unable to load reel';
  document.querySelectorAll('button, input').forEach(control => control.disabled = true);
}
