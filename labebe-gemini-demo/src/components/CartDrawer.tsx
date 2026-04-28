import { useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, Minus, Plus, ShoppingBag, Trash2, X } from 'lucide-react';
import { useCart } from '../context/useCart';
import { formatPrice, products } from '../data/products';

export default function CartDrawer({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { lines, subtotal, updateQuantity, removeItem, addItem } = useCart();
  const [checkoutReady, setCheckoutReady] = useState(false);
  const giftAddOn = products['llama-plush-rocker'];

  if (!isOpen) return null;

  return (
    <>
      <button className="cart-backdrop" type="button" aria-label="Close cart" onClick={onClose} />
      <aside className="cart-drawer" aria-label="Shopping cart">
        <div className="cart-drawer-header">
          <h2>
            <ShoppingBag size={22} />
            Your cart
          </h2>
          <button className="icon-only cart-close" type="button" onClick={onClose} aria-label="Close cart">
            <X size={20} />
          </button>
        </div>

        <div className="cart-drawer-body">
          {lines.length === 0 ? (
            <div className="cart-empty">
              <ShoppingBag size={28} />
              <h3>Your playroom plan is empty.</h3>
              <p>Start with a giftable rocker, a room reset piece, or a pretend-play world.</p>
              <Link to="/collections/giftable-rockers" className="primary-action" onClick={onClose}>
                Shop gifts
              </Link>
            </div>
          ) : (
            lines.map((line) => (
              <div className="cart-line" key={line.product.slug}>
                <img src={line.product.image} alt={line.product.title} />
                <div>
                  <Link to={`/product/${line.product.slug}`} onClick={onClose}>
                    {line.product.title}
                  </Link>
                  <span>{line.product.world}</span>
                  <strong>{formatPrice(line.product.price)}</strong>
                  <div className="quantity-stepper" aria-label={`Quantity for ${line.product.title}`}>
                    <button
                      type="button"
                      onClick={() => updateQuantity(line.product.slug, line.quantity - 1)}
                      aria-label="Decrease quantity"
                    >
                      <Minus size={14} />
                    </button>
                    <em>{line.quantity}</em>
                    <button
                      type="button"
                      onClick={() => updateQuantity(line.product.slug, line.quantity + 1)}
                      aria-label="Increase quantity"
                    >
                      <Plus size={14} />
                    </button>
                    <button
                      className="remove-line"
                      type="button"
                      onClick={() => removeItem(line.product.slug)}
                      aria-label={`Remove ${line.product.title}`}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}

          {giftAddOn && (
            <div className="cart-addon">
              <img src={giftAddOn.image} alt={giftAddOn.title} />
              <div>
                <span>Gift pairing</span>
                <strong>{giftAddOn.title}</strong>
                <em>{formatPrice(giftAddOn.price)}</em>
              </div>
              <button type="button" onClick={() => addItem(giftAddOn)}>
                Add
              </button>
            </div>
          )}

          {checkoutReady && lines.length > 0 && (
            <div className="checkout-handoff" role="status" aria-live="polite">
              <CheckCircle2 size={20} />
              <div>
                <strong>Cart summary ready</strong>
                <p>
                  Items, quantities, and subtotal are ready for checkout handoff.
                  Payment, tax, and shipping rules are handled in the final checkout service.
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="cart-drawer-footer">
          <div>
            <span>Subtotal</span>
            <strong>{formatPrice(subtotal)}</strong>
          </div>
          <p>Shipping and taxes are calculated at checkout.</p>
          <button
            className="primary-action cart-checkout"
            disabled={lines.length === 0}
            type="button"
            onClick={() => setCheckoutReady(true)}
          >
            Review checkout
          </button>
        </div>
      </aside>
    </>
  );
}
