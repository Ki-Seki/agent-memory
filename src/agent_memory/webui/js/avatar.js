// A profile's picture, drawn from its name so it is the same everywhere: soft blurred shapes on a pastel
// ground, after the "marble" style of Boring Avatars (https://github.com/boringdesigners/boring-avatars),
// with a small face on top.
//
// MIT License. Copyright (c) 2021 boringdesigners. Permission is hereby granted, free of charge, to any person
// obtaining a copy of this software and associated documentation files (the "Software"), to deal in the
// Software without restriction, including without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions: The above copyright notice and this permission
// notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED
// "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
// COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT
// OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.
import { raw } from "./h.js";

const COLORS = ["#c9c3ff", "#f7c6d9", "#ffdcb5", "#bfe6dd", "#a9c8ff", "#e6d4ff", "#ffeebd"];
const INK = "#29234d";

function hash(text) {
  let h = 0;
  for (const c of text) h = ((h << 5) - h + c.charCodeAt(0)) | 0;
  return Math.abs(h);
}
const digit = (n, i) => Math.floor((n / 10 ** i) % 10);
/** n mod range, negative when the i-th digit of n is even: how far, and which way, to move a shape. */
const unit = (n, range, i) => (i && digit(n, i) % 2 === 0 ? -(n % range) : n % range);

/** The ground and two blurred shapes; the blur is #pav-blur in index.html. */
function marble(n) {
  const color = (i) => COLORS[(n + i) % COLORS.length];
  const at = (i) => `translate(${unit(n * (i + 1), 8, 1)} ${unit(n * (i + 1), 8, 2)}) rotate(${unit(n * (i + 1), 360, 1)} 40 40) scale(${1.2 + unit(n * 3, 4) / 10})`;
  return `<rect width="80" height="80" fill="${color(0)}"/>`
    + `<path filter="url(#pav-blur)" d="M32.414 59.35L50.376 70.5H72.5v-71H33.728L26.5 13.381l19.057 27.08L32.414 59.35z" fill="${color(1)}" transform="${at(1)}"/>`
    + `<path filter="url(#pav-blur)" style="mix-blend-mode:overlay" d="M22.216 24L0 46.75l14.108 38.129L78 86l-3.081-59.276-22.378 4.005 12.972 20.186-23.35 27.395L22.215 24z" fill="${color(2)}" transform="${at(2)}"/>`;
}

/** Two eyes (dots, or closed and smiling) and a mouth, tilted a little, from a second hash of the name. */
function face(n) {
  const k = 1.5, w = 2.4 * k, eyeY = 35, mouthY = eyeY + 10 * k, spread = (9 + (n % 3)) * k;
  const line = (d) => `<path d="${d}" fill="none" stroke="${INK}" stroke-width="${w}" stroke-linecap="round"/>`;
  const eye = (x) => (n % 3 === 0
    ? line(`M${x - 3 * k} ${eyeY + 1.5 * k}q${3 * k} ${-3.4 * k} ${6 * k} 0`)
    : `<rect x="${x - 1.8 * k}" y="${eyeY - 3 * k}" width="${3.6 * k}" height="${(n % 3 === 1 ? 6 : 5) * k}" rx="${1.8 * k}" fill="${INK}"/>`);
  const mouth = [
    line(`M${40 - 5.5 * k} ${mouthY}q${5.5 * k} ${4.2 * k} ${11 * k} 0`),
    `<path d="M${40 - 5 * k} ${mouthY - 0.5 * k}a${5 * k} ${4 * k} 0 0 0 ${10 * k} 0z" fill="${INK}"/>`,
    line(`M${40 - 3.5 * k} ${mouthY}q${3.5 * k} ${2.6 * k} ${7 * k} 0`),
  ][digit(n, 4) % 3];
  const move = `translate(${unit(n, 6, 2) * 0.5} ${unit(n, 5, 3) * 0.4}) rotate(${unit(n, 10, 1)} 40 40)`;
  return `<g transform="${move}" opacity=".9">${eye(40 - spread)}${eye(40 + spread)}${mouth}</g>`;
}

/** The picture's colours alone, without its face or corners: Settings blurs it into a glow behind the profile. */
export function glow(name) {
  return raw(`<svg viewBox="0 0 80 80" preserveAspectRatio="none" aria-hidden="true">${marble(hash(name))}</svg>`);
}

/** The picture for a profile called `name`, sized by CSS (.pavatar); its rounded corners are #pav-clip. */
export function avatar(name, cls = "") {
  return raw(`<svg class="pavatar ${cls}" viewBox="0 0 80 80" aria-hidden="true"><g clip-path="url(#pav-clip)">${marble(hash(name))}${face(hash(`${name}face`))}</g></svg>`);
}
