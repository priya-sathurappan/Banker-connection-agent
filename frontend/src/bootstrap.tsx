// Standalone harness: stands in for the parent container during local development.
// It mounts the MFE exactly as a parent would, with no props.
import { mount } from "./mount";

const host = document.getElementById("root")!;
host.innerHTML = `
  <header style="background:#d71e28;color:#fff;padding:14px 24px;font-size:20px;font-weight:600">
    Parent container <span style="font-weight:400;font-size:14px;opacity:.85">(standalone harness)</span>
  </header>
  <main style="max-width:960px;margin:32px auto;padding:0 16px">
    <div id="bcw-slot"></div>
  </main>`;

mount(document.getElementById("bcw-slot")!);
