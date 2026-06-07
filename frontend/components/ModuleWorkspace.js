'use client';

import Link from 'next/link';
import { useMemo } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import ClientModulePage from './ClientModulePage';
import StaffActionPanel from './StaffActionPanel';

const FINANCE_ACTIONS = [
  {
    href: '/cashflow/receivables?action=collect',
    label: 'Receive Payment',
    note: 'Collect guest, OTA, event, or company balances.',
  },
  {
    href: '/cashflow/money-out?preset=operating-expense',
    label: 'Record Expense',
    note: 'Record spending from petty cash, bank, GCash, or card.',
  },
  {
    href: '/cashflow/payables?action=pay',
    label: 'Pay Supplier',
    note: 'Pay an open supplier bill and update the balance.',
  },
  {
    href: '/cashflow/daily-cash',
    label: 'Count Cash',
    note: 'Count drawer, petty cash, safe, or periodic bank balances.',
  },
  {
    href: '/cashflow/reconciliation?tab=bank',
    label: 'Check Banks',
    note: 'Use for periodic bank review or period closing.',
  },
];

const CONFIG = {
  rooms: {
    title: 'Rooms & Guests',
    description: 'Front desk operations in one place: guests, bookings, folios, setup, and room records.',
    tabs: [
      {
        key: 'overview',
        label: 'Overview',
        type: 'links',
        links: [
          ['/bookings', 'Bookings', 'Create and manage reservations'],
          ['/guests', 'Guests', 'Guest CRM with VIP and returning indicators'],
          ['/room-folios', 'Folios', 'Charges, payments, deposits, and balances'],
          ['/channel-payouts', 'Channel Payouts', 'Track expected and actual OTA payouts'],
        ],
      },
      {
        key: 'workflows',
        label: 'Workflows',
        type: 'links',
        links: [
          ['/bookings', 'Booking Workflow', 'Reserve, check in/out, and update status'],
          ['/room-folios', 'Folio Workflow', 'Add room charges and settle balances'],
          ['/guests', 'Guest Workflow', 'Find returning guests and update profiles'],
        ],
      },
      {
        key: 'setup',
        label: 'Setup',
        type: 'links',
        links: [
          ['/room-types', 'Room Types', 'Define room type codes and capacities'],
          ['/rooms', 'Rooms', 'Maintain room inventory and room-to-type links'],
          ['/rate-plans', 'Rate Plans', 'Define pricing and inclusions'],
          ['/booking-channels', 'Booking Channels', 'Setup OTA and direct channels'],
          ['/room-package-rules', 'Package Rules', 'Define package inclusions by room/rate'],
        ],
      },
      { key: 'records', label: 'Records', type: 'records' },
    ],
  },

  events: {
    title: 'Events',
    description: 'Dedicated event workflow for quotes, confirmation, deposits, AR balances, and completion.',
    tabs: [
      {
        key: 'overview',
        label: 'Overview',
        type: 'links',
        links: [
          ['/events', 'Events Workflow', 'Quote, confirm, collect deposits, and complete events'],
          ['/cashflow/receivables', 'Event Balances', 'Review unpaid event balances created from events'],
          ['/reports', 'Reports', 'Review event-related income when posted'],
        ],
      },
      {
        key: 'workflows',
        label: 'Workflows',
        type: 'links',
        links: [
          ['/events', 'Create Event Quote', 'Capture client, schedule, venue, package, and quote lines'],
          ['/events', 'Confirm Event', 'Post event income to AR and create the collection balance'],
          ['/events', 'Receive Event Payment', 'Collect deposits or balances without duplicate revenue'],
        ],
      },
      { key: 'records', label: 'Records', type: 'records' },
    ],
  },

  restaurant: {
    title: 'Restaurant & F&B',
    description: 'Restaurant operations, menu/recipe management, and F&B linked records.',
    tabs: [
      {
        key: 'overview',
        label: 'Overview',
        type: 'links',
        links: [
          ['/restaurant-ops', 'Operations & Advanced Tools', 'POS-outage sales, quick restock, variants, components, and promotions'],
          ['/menu-items', 'Menu & Recipes', 'Manage menu items, recipes, and SKUs'],
          ['/menu-categories', 'Menu Categories', 'Maintain category grouping for menu items'],
          ['/setup-imports', 'Excel Setup Import', 'Upload menu, variants, recipes, and ingredients'],
          ['/recipes', 'Recipes', 'Quick route to recipe maintenance'],
          ['/staff-meals', 'Staff Meals', 'Track staff meal ingredient usage'],
          ['/workspace/breakfast', 'Breakfast', 'Breakfast record workspace'],
          ['/workspace/cafe', 'Cafe', 'Cafe record workspace'],
          ['/workspace/bar', 'Bar', 'Bar record workspace'],
        ],
      },
      {
        key: 'workflows',
        label: 'Workflows',
        type: 'links',
        links: [
          ['/restaurant-ops', 'Fallback Sales Workflow', 'Use only when Cloud POS is unavailable'],
          ['/menu-items', 'Menu Workflow', 'Create dishes and update recipes'],
          ['/staff-meals', 'Staff Meal Workflow', 'Post internal meal consumption'],
        ],
      },
      { key: 'records', label: 'Records', type: 'records' },
    ],
  },

  inventory: {
    title: 'Inventory & Purchasing',
    description: 'Inventory control and procurement workflow in one workspace.',
    tabs: [
      {
        key: 'overview',
        label: 'Overview',
        type: 'links',
        links: [
          ['/inventory-items', 'Inventory Items', 'Item setup and reorder levels'],
          ['/setup-imports', 'Excel Setup Import', 'Upload inventory items, units, categories, and recipes'],
          ['/stock-movements', 'Stock Movements', 'FIFO stock-in/out movement log'],
          ['/suppliers', 'Suppliers', 'Supplier master linked to procurement/payables'],
          ['/purchase-requests', 'Purchase Requests', 'PR workflow with status'],
          ['/purchase-orders', 'Purchase Orders', 'PO workflow with receiving progress'],
          ['/receiving', 'Receiving', 'Receiving workflow with stock and payable impact'],
          ['/inventory-reconciliation', 'Inventory Reconciliation', 'Physical count adjustments'],
        ],
      },
      {
        key: 'workflows',
        label: 'Workflows',
        type: 'links',
        links: [
          ['/purchase-requests', 'PR Workflow', 'Draft, submit, approve, convert'],
          ['/purchase-orders', 'PO Workflow', 'Issue, monitor, and complete orders'],
          ['/receiving', 'Receiving Workflow', 'Post deliveries and update stock'],
          ['/stock-movements', 'Stock Workflow', 'Review movement and cost trail'],
        ],
      },
      { key: 'records', label: 'Records', type: 'records' },
    ],
  },

  payroll: {
    title: 'People & Payroll',
    description: 'Employee and payroll period workflow with attendance and approvals.',
    tabs: [
      {
        key: 'overview',
        label: 'Overview',
        type: 'links',
        links: [
          ['/employees', 'Employees', 'Employee registry and details'],
          ['/attendance', 'Attendance', 'Attendance input and review'],
          ['/payroll-periods', 'Payroll Periods', 'Main payroll period workflow'],
          ['/approvals', 'Approvals', 'Approval queue for pending actions'],
        ],
      },
      {
        key: 'workflows',
        label: 'Workflows',
        type: 'links',
        links: [
          ['/payroll-periods', 'Payroll Period Workflow', 'Input/import, post, and report'],
          ['/attendance', 'Attendance Workflow', 'Capture and validate period attendance'],
          ['/approvals', 'Approval Workflow', 'Approve payroll/procurement/accounting items'],
        ],
      },
      { key: 'records', label: 'Records', type: 'records' },
    ],
  },

  finance: {
    title: 'Finance & Accounting',
    description: 'Cashflow operations plus accounting, reporting, assets, and BIR.',
    tabs: [
      {
        key: 'overview',
        label: 'Overview',
        type: 'links',
        links: [
          ['/cashflow', 'Cashflow', 'Money in, money out, transfers, and checks'],
          ['/journals', 'Journals', 'Journal entries and trial balance'],
          ['/reports', 'Reports', 'Operational and accounting reports'],
          ['/assets', 'Assets', 'Asset registry and lifecycle logs'],
          ['/bir', 'BIR', 'Candidate selection, books, and locks'],
        ],
      },
      {
        key: 'workflows',
        label: 'Workflows',
        type: 'links',
        links: [
          ['/cashflow/money-in', 'Money In', 'Record incoming funds'],
          ['/cashflow/money-out', 'Money Out', 'Record disbursements'],
          ['/cashflow/transfers', 'Transfers', 'Move funds between drawers/banks'],
          ['/cashflow/daily-cash', 'Cash Count', 'Count drawers, petty cash, safe, or periodic bank balance'],
          ['/cashflow/reconciliation', 'Periodic Checks', 'Review cash, bank, OTA, payment, and bill exceptions'],
          ['/cashflow/receivables', 'To Receive', 'Track and collect open balances'],
          ['/cashflow/payables', 'To Pay', 'Track and pay open bills'],
        ],
      },
      { key: 'records', label: 'Records', type: 'records' },
    ],
  },

  settings: {
    title: 'Settings',
    description: 'Admin tools only: setup, users, permissions, and accounting configuration.',
    tabs: [
      {
        key: 'overview',
        label: 'Overview',
        type: 'links',
        links: [
          ['/master-data', 'Master Data', 'Generic reusable values'],
          ['/taxonomy-admin', 'Accounting Taxonomy', 'Accounting classification maintenance'],
          ['/users', 'Users', 'Manage user accounts and role assignments'],
          ['/roles-permissions', 'Roles & Permissions', 'Checklist permissions per role'],
          ['/chart-of-accounts', 'Chart of Accounts', 'Maintain account structures'],
          ['/account-mapping', 'Account Mapping', 'Maintain posting mapping rules'],
          ['/integrations/beds24', 'Beds24 Integration', 'Sync Beds24 bookings into ERP'],
          ['/system-settings', 'System Settings', 'Workflow and system-level controls'],
        ],
      },
      {
        key: 'system',
        label: 'System',
        type: 'links',
        links: [
          ['/roles-permissions', 'Access Control', 'Role-permission governance'],
          ['/chart-of-accounts', 'Accounting Setup', 'Core account setup'],
          ['/account-mapping', 'Posting Setup', 'Accounting posting mappings'],
          ['/integrations/beds24', 'Integrations', 'External system connection controls'],
          ['/system-settings', 'System Controls', 'Cross-module workflow controls'],
        ],
      },
    ],
  },
};

function TabButton({ active, onClick, children }) {
  return (
    <button type="button" className={active ? 'tab active' : 'tab'} onClick={onClick}>
      {children}
    </button>
  );
}

function LinksGrid({ links = [] }) {
  return (
    <div className="card-grid">
      {links.map(([href, label, note]) => (
        <Link href={href} key={href} className="card card-link">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <strong>{label}</strong>
            <span>→</span>
          </div>
          <div className="muted small">{note}</div>
        </Link>
      ))}
      {!links.length && (
        <section className="section">
          <p className="muted">No links in this tab yet.</p>
        </section>
      )}
    </div>
  );
}

export default function ModuleWorkspace({ moduleSlug }) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const config = CONFIG[moduleSlug] || {
    title: moduleSlug,
    description: 'Module workspace.',
    tabs: [{ key: 'records', label: 'Records', type: 'records' }],
  };

  const tabs = config.tabs || [];
  const tabParam = searchParams.get('tab');
  const activeTab = useMemo(() => {
    if (!tabs.length) return { key: 'records', label: 'Records', type: 'records' };
    return tabs.find((tab) => tab.key === tabParam) || tabs[0];
  }, [tabParam, tabs]);

  function setTab(nextTab) {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', nextTab);
    router.replace(`/workspace/${moduleSlug}?${params.toString()}`);
  }

  return (
    <div>
      <section className="section">
        <h1>{config.title}</h1>
        <p className="muted">{config.description}</p>
        <div className="tabs">
          {tabs.map((tab) => (
            <TabButton key={tab.key} active={activeTab.key === tab.key} onClick={() => setTab(tab.key)}>
              {tab.label}
            </TabButton>
          ))}
        </div>
      </section>

      {moduleSlug === 'finance' && activeTab.key === 'overview' && <StaffActionPanel title="Common Finance Work" actions={FINANCE_ACTIONS} />}

      {activeTab.type === 'records' && (
        <ClientModulePage
          moduleSlug={moduleSlug}
          compactTitle
          categoryFilter={activeTab.categoryFilter || []}
          defaultCategory={activeTab.defaultCategory || ''}
          defaultBucket={activeTab.defaultBucket || ''}
        />
      )}

      {activeTab.type === 'links' && <LinksGrid links={activeTab.links || []} />}
    </div>
  );
}
