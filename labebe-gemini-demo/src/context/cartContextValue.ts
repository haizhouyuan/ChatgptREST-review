import { createContext } from 'react';
import type { Product } from '../data/products';

export type CartLine = {
  product: Product;
  quantity: number;
};

export type CartContextValue = {
  lines: CartLine[];
  count: number;
  subtotal: number;
  addItem: (product: Product) => void;
  removeItem: (slug: string) => void;
  updateQuantity: (slug: string, quantity: number) => void;
  clearCart: () => void;
};

export const CartContext = createContext<CartContextValue | undefined>(undefined);
