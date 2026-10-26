import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the finance module. Titles are provisional (see RouteSpec.title). */
export const financeRouteSpecs: readonly RouteSpec[] = [
  {
    path: '/finance',
    title: 'Finance & billing',
    module: 'finance',
    layout: 'app',
    screenshots: ['15-finance.png'],
    titleSource: 'demo',
  },
  { path: '/finance/invoices', title: 'Invoices', module: 'finance', layout: 'app' },
  { path: '/finance/invoices/new', title: 'New invoice', module: 'finance', layout: 'app' },
  {
    path: '/finance/invoices/:id',
    title: 'Invoice',
    module: 'finance',
    layout: 'app',
    screenshots: ['14-invoice.png'],
  },
  { path: '/finance/expenses', title: 'Expenses', module: 'finance', layout: 'app' },
];
