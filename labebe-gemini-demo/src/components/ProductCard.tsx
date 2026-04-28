import { Link } from 'react-router-dom';
import { ArrowRight, ShoppingBag } from 'lucide-react';
import type { Product } from '../data/products';
import { formatPrice } from '../data/products';

type Props = {
  product: Product;
  compact?: boolean;
};

export default function ProductCard({ product, compact = false }: Props) {
  return (
    <article className={`product-card ${compact ? 'compact' : ''}`}>
      <Link to={`/product/${product.slug}`} className="product-image-link" aria-label={product.title}>
        <img src={product.image} alt={product.title} />
        <div className="card-badges">
          {product.badges.slice(0, 2).map((badge) => (
            <span className="badge" key={badge}>
              {badge}
            </span>
          ))}
        </div>
      </Link>

      <div className="product-card-body">
        <div className="eyebrow-line">
          <span>{product.ageRange}</span>
          <span>{product.roomTags[0]}</span>
        </div>
        <Link to={`/product/${product.slug}`} className="product-title-link">
          <h3>{product.title}</h3>
        </Link>
        {!compact && <p>{product.shortBenefit}</p>}

        <div className="price-row">
          <strong>{formatPrice(product.price)}</strong>
          {product.compareAtPrice && <span>{formatPrice(product.compareAtPrice)}</span>}
          {product.reviewCount !== null && <em>{product.reviewCount} reviews</em>}
        </div>

        <div className="card-action-row">
          <Link className="secondary-action" to={`/product/${product.slug}`}>
            <ShoppingBag size={17} />
            View item
          </Link>
          <Link className="text-action" to={`/product/${product.slug}`} aria-label={`View ${product.title}`}>
            <ArrowRight size={17} />
          </Link>
        </div>
      </div>
    </article>
  );
}
