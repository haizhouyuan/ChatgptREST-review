import { Link, NavLink } from 'react-router-dom';
import { Gift, Home, Search, ShoppingBag } from 'lucide-react';
import { useCart } from '../context/useCart';

export default function Navigation({ onCartOpen }: { onCartOpen: () => void }) {
  const { count } = useCart();

  return (
    <header className="site-header labebe-header">
      <div className="container nav-inner">
        <Link to="/" className="brand-mark labebe-brand" aria-label="Labebe home">
          <span>Labebe</span>
          <small>Wooden toys & kids furniture</small>
        </Link>

        <nav className="desktop-nav labebe-nav" aria-label="Primary navigation">
          <NavLink to="/shop/by-room">Shop by Room</NavLink>
          <NavLink to="/shop/by-age">Shop by Age</NavLink>
          <NavLink to="/collections/giftable-rockers">Gifts</NavLink>
          <NavLink to="/collections/pretend-play-worlds">Play Worlds</NavLink>
          <NavLink to="/collections/playroom-reset">Storage</NavLink>
        </nav>

        <div className="nav-tools" aria-label="Shopping tools">
          <Link to="/shop/by-age" className="icon-nav" aria-label="Find a gift">
            <Gift size={17} />
            <span>Gift finder</span>
          </Link>
          <Link to="/shop/by-room" className="icon-nav" aria-label="Shop by room">
            <Home size={17} />
            <span>Rooms</span>
          </Link>
          <Link to="/collections/playroom-reset" className="icon-only" aria-label="Search room ideas">
            <Search size={18} />
          </Link>
          <button className="commerce-chip cart-trigger" type="button" onClick={onCartOpen}>
            <ShoppingBag size={16} />
            Cart
            {count > 0 && <span className="cart-count">{count}</span>}
          </button>
        </div>
      </div>
    </header>
  );
}
