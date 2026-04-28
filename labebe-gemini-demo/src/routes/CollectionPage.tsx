import { Link, useParams } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import ProductCard from '../components/ProductCard';
import { getWorld, WORLDS } from '../data/collections';
import { productList, products } from '../data/products';

type Props = {
  forcedMode?: 'age' | 'room';
};

export default function CollectionPage({ forcedMode }: Props) {
  const { id } = useParams<{ id: string }>();

  if (forcedMode === 'age') {
    return (
      <div className="collection-page">
        <section className="container collection-hero">
          <span className="section-kicker">Shop by Age</span>
          <h1>Find the right piece by stage, room, and occasion.</h1>
          <p>Start with the child's age range, then move into gifts, rooms, and play routines that fit daily family life.</p>
        </section>
        <AgeBlock
          title="6-18m"
          products={[
            'activity-cube-baby-push-walker',
            'activity-montessori-baby-push-walker',
            'classic-montessori-baby-push-walker',
            'ice-cream-cart-baby-push-walker',
            'farm-themed-baby-push-walker',
            'panda-baby-push-walker',
          ]}
        />
        <AgeBlock title="1-3Y" products={['pink-unicorn-plush-rocker', 'llama-plush-rocker', 'highlander-cattle-plush-rocker']} />
        <AgeBlock title="3-6Y" products={['cream-wooden-play-kitchen-set-with-storage', 'kids-coffee-shop-grocery-store-playset', 'natural-wood-montessori-shelf-with-storage-boxes']} />
      </div>
    );
  }

  if (forcedMode === 'room') {
    return (
      <div className="collection-page">
        <section className="container collection-hero">
          <span className="section-kicker">Shop by Room</span>
          <h1>Build a nursery, playroom, kitchen corner, or outdoor play setup.</h1>
          <p>Room-led browsing turns product discovery into a practical home-planning experience.</p>
        </section>
        <RoomBlock title="Nursery" />
        <RoomBlock title="Playroom" />
        <RoomBlock title="Kitchen" />
        <RoomBlock title="Outdoor" />
      </div>
    );
  }

  const world = getWorld(id) || WORLDS[0];
  const collectionProducts = world.productSlugs.map((slug) => products[slug]).filter(Boolean);

  return (
    <div className="collection-page">
      <section className="container collection-hero">
        <span className="section-kicker">{world.productCount} products</span>
        <h1>{world.name}</h1>
        <p>{world.description}</p>
        <small>{world.bestFor}</small>
      </section>

      <section className="container product-grid three">
        {collectionProducts.map((product) => (
          <ProductCard key={product.slug} product={product} />
        ))}
      </section>

      <section className="container collection-note">
        <h2>Easy next step</h2>
        <p>
          Match the collection to the child’s age, the room it will live in, and the occasion
          that makes it worth choosing now.
        </p>
        <Link to="/shop/by-age">
          Find by age <ArrowRight size={15} />
        </Link>
      </section>
    </div>
  );
}

function AgeBlock({ title, products: slugs }: { title: string; products: string[] }) {
  const items = slugs.map((slug) => products[slug]).filter(Boolean);
  return (
    <section className="container age-block">
      <div className="section-heading split">
        <h2>{title}</h2>
        <p>{items.length} recommendations for this stage.</p>
      </div>
      <div className="product-grid three">
        {items.map((product) => (
          <ProductCard key={product.slug} product={product} />
        ))}
      </div>
    </section>
  );
}

function RoomBlock({ title }: { title: string }) {
  const items = productList.filter((product) => product.roomTags.includes(title)).slice(0, 6);
  return (
    <section className="container age-block">
      <div className="section-heading split">
        <h2>{title}</h2>
        <p>{items.length} products for this room.</p>
      </div>
      <div className="product-grid three">
        {items.map((product) => (
          <ProductCard key={product.slug} product={product} />
        ))}
      </div>
    </section>
  );
}
