'use client';
import LegacyExternalModuleNotice from '../../components/LegacyExternalModuleNotice';

import ClientModulePage from '../../components/ClientModulePage';

export default function InventoryReconciliationPage() {
  return (
    <div>
      <LegacyExternalModuleNotice appName="Inventory & Procurement" />
      <div className="stack">
      <section className="section">
        <h1>Inventory Reconciliation</h1>
        <p className="muted">
          Post physical count variances, gains/losses, and correction entries for inventory reconciliation.
        </p>
      </section>
      <ClientModulePage
        moduleSlug="reconciliation"
        compactTitle
        categoryFilter={['Inventory Reconciliation']}
        defaultCategory="Inventory Reconciliation"
      />
      </div>
    </div>
  );
}