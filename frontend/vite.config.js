import { defineConfig } from 'vite';
export default defineConfig({ plugins: [{
  name: 'hhe-build-info',
  generateBundle() {
    this.emitFile({ type: 'asset', fileName: 'build-info.json', source: JSON.stringify({
      application: 'Hardware History Explorer', ui_version: '2026-11-europe-1',
      built_at: new Date().toISOString(),
      features: ['simple_release_citations', 'european_configuration_groups', 'european_release_groups']
    }, null, 2) });
  }
}], server: { proxy: {
  '/api': 'http://localhost:8000',
  '/media': 'http://localhost:8000'
} } });
