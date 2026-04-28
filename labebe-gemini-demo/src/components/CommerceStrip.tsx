import { Link, useLocation } from 'react-router-dom';
import { ArrowRight, Box, FileCheck2, ShoppingCart } from 'lucide-react';
import { formatPrice, products } from '../data/products';

export default function CommerceStrip() {
  const hero = products['pink-unicorn-plush-rocker'];
  const { pathname } = useLocation();

  if (pathname === '/') {
    return null;
  }

  const active = pathname.startsWith('/ai-growth-demo')
    ? 'matrix'
    : pathname.startsWith('/boss-demo')
      ? 'scan'
      : pathname.startsWith('/product')
        ? 'pdp'
        : 'scan';

  return (
    <aside className="global-commerce-strip" aria-label="Persistent commerce output">
      <div className="strip-product">
        <Box size={16} />
        <span>{hero.title}</span>
        <strong>{formatPrice(hero.price)}</strong>
      </div>
      <div className="strip-thesis">1 SKU {'->'} 7 assets {'->'} claim-gated {'->'} PDP ready</div>
      <nav className="strip-actions" aria-label="Commerce and matrix actions">
        <Link to="/product/pink-unicorn-plush-rocker" className={active === 'pdp' ? 'active' : ''}>
          <ShoppingCart size={15} />
          View PDP
        </Link>
        <Link to="/ai-growth-demo" className={active === 'matrix' ? 'active' : ''}>
          <FileCheck2 size={15} />
          Matrix
        </Link>
        <Link to="/boss-demo" className={active === 'scan' ? 'active' : ''}>
          Scan
          <ArrowRight size={15} />
        </Link>
      </nav>
    </aside>
  );
}
