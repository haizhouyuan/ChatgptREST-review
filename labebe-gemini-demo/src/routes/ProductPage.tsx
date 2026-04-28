import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ArrowRight,
  Heart,
  PackageCheck,
  Ruler,
  ShieldCheck,
  ShoppingBag,
  Truck,
  Wrench,
} from 'lucide-react';
import ProductCard from '../components/ProductCard';
import { useCart } from '../context/useCart';
import { formatPrice, getBundleProducts, getProduct } from '../data/products';

type ProductTab = 'details' | 'fit' | 'gift';

const collectionHrefByWorld: Record<string, string> = {
  'Giftable Rockers': '/collections/giftable-rockers',
  'Montessori at Home': '/collections/montessori-at-home',
  'Tiny Pretend Worlds': '/collections/pretend-play-worlds',
  'Playroom Reset': '/collections/playroom-reset',
  'Outdoor Pretend Play': '/collections/pretend-play-worlds',
  'Milestone Activity': '/shop/by-age',
  'Study & Art Corner': '/shop/by-room',
};

export default function ProductPage({ onCartOpen }: { onCartOpen: () => void }) {
  const { slug } = useParams<{ slug: string }>();
  const product = getProduct(slug);
  const [tab, setTab] = useState<ProductTab>('details');
  const { addItem } = useCart();

  if (!product) {
    return (
      <div className="empty-state container">
        <h1>Product not found</h1>
        <Link to="/" className="primary-action">
          Return home
        </Link>
      </div>
    );
  }

  const bundle = getBundleProducts(product).slice(0, 3);
  const collectionHref = collectionHrefByWorld[product.world] || '/';
  const bestFor = product.giftTags[0] || product.playTags[0];

  return (
    <div className="pdp-page">
      <div className="container breadcrumb">
        <Link to="/">Home</Link>
        <span>/</span>
        <Link to={collectionHref}>{product.world}</Link>
        <span>/</span>
        <strong>{product.title}</strong>
      </div>

      <section className="container pdp-grid pure-pdp-grid">
        <div className="pdp-gallery">
          <div className="main-product-image">
            <img src={product.image} alt={product.title} />
          </div>
          <div className="pdp-thumbs">
            <button className="active" type="button">
              <img src={product.image} alt={`${product.title} product view`} />
            </button>
            <button type="button">
              <span>Room</span>
            </button>
            <button type="button">
              <span>Detail</span>
            </button>
            <button type="button">
              <span>Gift</span>
            </button>
          </div>
        </div>

        <div className="pdp-info pure-pdp-info">
          <span className="section-kicker">{product.world}</span>
          <h1>{product.title}</h1>
          <p className="pdp-benefit">{product.shortBenefit}</p>

          <div className="pdp-price-row">
            <strong>{formatPrice(product.price)}</strong>
            {product.compareAtPrice && <span>{formatPrice(product.compareAtPrice)}</span>}
            {product.reviewCount !== null && <em>{product.reviewCount} reviews</em>}
          </div>

          <div className="pdp-badges">
            <span>Age: {product.ageRange}</span>
            <span>Room: {product.roomTags.join(' / ')}</span>
            <span>Best for: {bestFor}</span>
          </div>

          <div className="product-intent-list">
            {product.playTags.slice(0, 3).map((tag) => (
              <span key={tag}>{tag}</span>
            ))}
          </div>

          <div className="pdp-actions">
            <button
              className="primary-action"
              type="button"
              onClick={() => {
                addItem(product);
                onCartOpen();
              }}
            >
              <ShoppingBag size={19} />
              Add to cart
            </button>
            <Link to={collectionHref} className="secondary-action wide">
              Explore collection
              <ArrowRight size={17} />
            </Link>
          </div>

          <div className="pdp-service-row" aria-label="Shopping confidence">
            <span><Truck size={16} /> Shipping calculated at checkout</span>
            <span><Heart size={16} /> Works with room and gift bundles</span>
          </div>

          <div className="lens-tabs" role="tablist" aria-label="Product details">
            {[
              ['details', 'Details'],
              ['fit', 'Fit & care'],
              ['gift', 'Gifting'],
            ].map(([id, label]) => (
              <button
                key={id}
                className={tab === id ? 'active' : ''}
                onClick={() => setTab(id as ProductTab)}
                type="button"
              >
                {label}
              </button>
            ))}
          </div>

          <ProductTabPanel tab={tab} productTitle={product.title} ageRange={product.ageRange} bestFor={bestFor} />
        </div>
      </section>

      <section className="container pdp-modules">
        <div className="module-card">
          <ShieldCheck size={22} />
          <h3>Safety-minded shopping</h3>
          <p>Clear age guidance, room context, and care notes stay close to the buying decision.</p>
        </div>
        <div className="module-card">
          <Ruler size={22} />
          <h3>Room fit</h3>
          <p>Room tags keep nursery, playroom, kitchen, bedroom, and outdoor placement easy to compare.</p>
        </div>
        <div className="module-card">
          <Wrench size={22} />
          <h3>Assembly & care</h3>
          <p>Practical setup, cleaning, and storage notes help parents understand the whole ownership moment.</p>
        </div>
      </section>

      <section className="container home-fit-section">
        <div>
          <span className="section-kicker">How it fits at home</span>
          <h2>From product page to a complete room moment.</h2>
          <p>
            See where it belongs, what it pairs with, and when it makes sense as a gift before
            moving back into the full catalog.
          </p>
        </div>
        <div className="home-fit-steps">
          {[
            ['01', 'Place it', `Fits naturally in the ${product.roomTags[0].toLowerCase()} story.`],
            ['02', 'Pair it', bundle[0] ? `Pairs well with ${bundle[0].title}.` : 'Pair with a related room piece.'],
            ['03', 'Gift it', product.giftTags[0] ? `Best framed as a ${product.giftTags[0].toLowerCase()}.` : `Best framed around ${product.playTags[0].toLowerCase()}.`],
          ].map(([number, title, copy]) => (
            <div className="home-fit-step" key={number}>
              <span>{number}</span>
              <strong>{title}</strong>
              <p>{copy}</p>
            </div>
          ))}
        </div>
      </section>

      {bundle.length > 0 && (
        <section className="container bundle-section">
          <div className="section-heading split">
            <div>
              <span className="section-kicker">Complete the moment</span>
              <h2>Pair it with room-friendly pieces.</h2>
            </div>
            <p>Suggested pairings are selected by room, age range, and play scenario.</p>
          </div>
          <div className="product-grid three">
            {bundle.map((item) => (
              <ProductCard key={item.slug} product={item} compact />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function ProductTabPanel({
  tab,
  productTitle,
  ageRange,
  bestFor,
}: {
  tab: ProductTab;
  productTitle: string;
  ageRange: string;
  bestFor: string;
}) {
  if (tab === 'fit') {
    return (
      <div className="lens-panel">
        <PackageCheck size={20} />
        <h3>Designed for everyday placement</h3>
        <p>Use the room tags and final dimension data to choose a nursery, playroom, kitchen, or bedroom placement.</p>
      </div>
    );
  }

  if (tab === 'gift') {
    return (
      <div className="lens-panel">
        <Heart size={20} />
        <h3>Gift framing</h3>
        <p>{productTitle} is best merchandised around {bestFor.toLowerCase()} moments, with clear age guidance for {ageRange}.</p>
      </div>
    );
  }

  return (
    <div className="lens-panel">
      <ShieldCheck size={20} />
      <h3>Product details</h3>
      <p>Price, age range, room fit, product imagery, and available review counts are kept together for faster comparison.</p>
    </div>
  );
}
