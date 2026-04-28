import { BrowserRouter as Router, Navigate, Route, Routes } from 'react-router-dom';
import { useState } from 'react';
import CartDrawer from './components/CartDrawer';
import Navigation from './components/Navigation';
import { CartProvider } from './context/CartContext';
import Home from './routes/Home';
import ProductPage from './routes/ProductPage';
import CollectionPage from './routes/CollectionPage';

function App() {
  const [cartOpen, setCartOpen] = useState(false);

  return (
    <CartProvider>
      <Router>
        <div className="app-shell labebe-site">
          <Navigation onCartOpen={() => setCartOpen(true)} />
          <main>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/product/:slug" element={<ProductPage onCartOpen={() => setCartOpen(true)} />} />
              <Route path="/collections/:id" element={<CollectionPage />} />
              <Route path="/shop/by-age" element={<CollectionPage forcedMode="age" />} />
              <Route path="/shop/by-room" element={<CollectionPage forcedMode="room" />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
          <CartDrawer isOpen={cartOpen} onClose={() => setCartOpen(false)} />
        </div>
      </Router>
    </CartProvider>
  );
}

export default App;
