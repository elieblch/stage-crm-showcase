// Tests unitaires de parseQuickAdd — Node test runner natif (0 dépendance).
// Exécuter : npm test  (→ node --test src/lib/quickAdd.test.ts)

import { test } from "node:test";
import assert from "node:assert/strict";

import { parseQuickAdd } from "./quickAdd.ts";

test("route un bloc offer vers le formulaire offre", () => {
  const r = parseQuickAdd(
    JSON.stringify({ type: "offer", title: "Stage M&A", company: "Lazard" })
  );
  assert.equal(r.ok, true);
  if (!r.ok) return;
  assert.equal(r.kind, "offer");
  assert.equal(r.fields.title, "Stage M&A");
  assert.equal(r.fields.company, "Lazard");
  // Défauts d'enum appliqués.
  assert.equal(r.fields.status, "a_postuler");
  assert.equal(r.fields.priority, "moyenne");
});

test("route un bloc contact vers le formulaire contact", () => {
  const r = parseQuickAdd(
    JSON.stringify({ type: "contact", name: "Jean Dupont", email: "jean@x.com" })
  );
  assert.equal(r.ok, true);
  if (!r.ok) return;
  assert.equal(r.kind, "contact");
  assert.equal(r.fields.name, "Jean Dupont");
  assert.equal(r.fields.email, "jean@x.com");
  assert.equal(r.fields.status, "a_contacter");
});

test("tolère un bloc entouré de fences ```json", () => {
  const block = "```json\n" + JSON.stringify({ type: "offer", title: "A", company: "X" }) + "\n```";
  const r = parseQuickAdd(block);
  assert.equal(r.ok, true);
  if (!r.ok) return;
  assert.equal(r.kind, "offer");
  assert.equal(r.fields.title, "A");
});

test("ignore les clés inconnues sans erreur", () => {
  const r = parseQuickAdd(
    JSON.stringify({ type: "contact", name: "Jean", inconnu: "x", autre: 42 })
  );
  assert.equal(r.ok, true);
  if (!r.ok) return;
  assert.equal(r.fields.name, "Jean");
  assert.equal(("inconnu" in r.fields), false);
});

test("enum invalide → valeur par défaut + warning", () => {
  const r = parseQuickAdd(
    JSON.stringify({ type: "offer", title: "A", company: "X", status: "n_importe_quoi", priority: "ultra" })
  );
  assert.equal(r.ok, true);
  if (!r.ok) return;
  assert.equal(r.fields.status, "a_postuler");
  assert.equal(r.fields.priority, "moyenne");
  assert.equal(r.warnings.length, 2);
});

test("enum vide → valeur par défaut + warning", () => {
  const r = parseQuickAdd(
    JSON.stringify({ type: "contact", name: "Jean", status: "" })
  );
  assert.equal(r.ok, true);
  if (!r.ok) return;
  assert.equal(r.fields.status, "a_contacter");
  assert.equal(r.warnings.length, 1);
});

test("enum valide conservée, sans warning", () => {
  const r = parseQuickAdd(
    JSON.stringify({ type: "offer", title: "A", company: "X", status: "entretien", priority: "haute" })
  );
  assert.equal(r.ok, true);
  if (!r.ok) return;
  assert.equal(r.fields.status, "entretien");
  assert.equal(r.fields.priority, "haute");
  assert.equal(r.warnings.length, 0);
});

test("deadline ISO conservée, deadline invalide ignorée + warning", () => {
  const ok = parseQuickAdd(JSON.stringify({ type: "offer", title: "A", company: "X", deadline: "2026-09-30" }));
  assert.equal(ok.ok, true);
  if (ok.ok) assert.equal(ok.fields.deadline, "2026-09-30");

  const bad = parseQuickAdd(JSON.stringify({ type: "offer", title: "A", company: "X", deadline: "bientôt" }));
  assert.equal(bad.ok, true);
  if (!bad.ok) return;
  assert.equal(bad.fields.deadline, undefined);
  assert.ok(bad.warnings.some((w) => w.toLowerCase().includes("deadline")));
});

test("deadline jj/mm/aaaa normalisée en ISO", () => {
  const r = parseQuickAdd(JSON.stringify({ type: "offer", title: "A", company: "X", deadline: "30/09/2026" }));
  assert.equal(r.ok, true);
  if (r.ok) assert.equal(r.fields.deadline, "2026-09-30");
});

test("JSON malformé → erreur claire, ne casse rien", () => {
  const r = parseQuickAdd('{ type: offer, oops }');
  assert.equal(r.ok, false);
  if (r.ok) return;
  assert.ok(r.error.length > 0);
});

test("type manquant → erreur", () => {
  const r = parseQuickAdd(JSON.stringify({ title: "A", company: "X" }));
  assert.equal(r.ok, false);
});

test("type inconnu → erreur", () => {
  const r = parseQuickAdd(JSON.stringify({ type: "facture", x: 1 }));
  assert.equal(r.ok, false);
});

test("bloc partiel toléré (champs absents ignorés)", () => {
  const r = parseQuickAdd(JSON.stringify({ type: "contact", name: "Jean" }));
  assert.equal(r.ok, true);
  if (!r.ok) return;
  assert.equal(r.fields.name, "Jean");
  assert.equal(r.fields.company, undefined);
  // Aucune valeur enum vide fournie → pas de warning.
  assert.equal(r.warnings.length, 0);
});

test("bloc vide → erreur", () => {
  assert.equal(parseQuickAdd("").ok, false);
  assert.equal(parseQuickAdd("   ").ok, false);
});
