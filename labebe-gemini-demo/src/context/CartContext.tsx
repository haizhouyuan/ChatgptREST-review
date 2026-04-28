import { useMemo, useState, type ReactNode } from 'react';
import { CartContext, type CartContextValue, type CartLine } from './cartContextValue';

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>([]);

  const value = useMemo<CartContextValue>(() => {
    const count = lines.reduce((sum, line) => sum + line.quantity, 0);
    const subtotal = lines.reduce((sum, line) => sum + line.product.price * line.quantity, 0);

    return {
      lines,
      count,
      subtotal,
      addItem: (product) => {
        setLines((current) => {
          const existing = current.find((line) => line.product.slug === product.slug);
          if (existing) {
            return current.map((line) =>
              line.product.slug === product.slug ? { ...line, quantity: line.quantity + 1 } : line,
            );
          }
          return [...current, { product, quantity: 1 }];
        });
      },
      removeItem: (slug) => {
        setLines((current) => current.filter((line) => line.product.slug !== slug));
      },
      updateQuantity: (slug, quantity) => {
        setLines((current) =>
          current
            .map((line) => (line.product.slug === slug ? { ...line, quantity: Math.max(0, quantity) } : line))
            .filter((line) => line.quantity > 0),
        );
      },
      clearCart: () => setLines([]),
    };
  }, [lines]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}
