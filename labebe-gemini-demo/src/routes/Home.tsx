import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Baby,
  Boxes,
  Check,
  Gift,
  Home as HomeIcon,
  MoveRight,
  Paintbrush,
  Ruler,
  Sparkles,
} from 'lucide-react';
import ProductCard from '../components/ProductCard';
import { WORLDS } from '../data/collections';
import { formatPrice, getBestSellers, giftFinderRecommendations, productList, products } from '../data/products';

const hero = products['pink-unicorn-plush-rocker'];
const crocodile = products['crocodile-plush-rocker'];
const swan = products['white-swan-plush-rocker'];
const fox = products['fox-plush-rocker'];
const kitchen = products['cream-wooden-play-kitchen-set-with-storage'];
const tower = products['foldable-learning-tower-montessori-kitchen-tower-log-color'];
const shelf = products['natural-wood-montessori-shelf-with-storage-boxes'];
const storage = products['kids-toy-storage-organizer-bookshelf-with-bins'];
const desk = products['children-s-writing-desk-and-chair-set-with-hutch---cork-board-for-study---art'];
const mudKitchen = products['wooden-mud-kitchen-outdoor-play-kitchen-with-planter-box-sink'];
const walker = products['activity-cube-baby-push-walker'];

const ageOptions = ['6-18m', '1-3Y', '3-6Y', '3-8Y'];
const roomOptions = ['Nursery', 'Playroom', 'Kitchen', 'Outdoor', 'Bedroom'];
const occasionOptions = ['First Birthday', 'Holiday Gift', 'Big Gift', 'Creative Gift'];

const missionCards = [
  {
    icon: Gift,
    title: 'Pick a gift that feels personal',
    copy: 'Start with age, occasion, and the room it will live in.',
    href: '/collections/giftable-rockers',
    product: hero,
    className: 'mission-gift',
  },
  {
    icon: HomeIcon,
    title: 'Build a calmer playroom',
    copy: 'Shop storage, low shelves, art corners, and product pairings as one room plan.',
    href: '/collections/playroom-reset',
    product: storage,
    className: 'mission-room',
  },
  {
    icon: Paintbrush,
    title: 'Create a tiny world',
    copy: 'Kitchen, cafe, laundry, garden and art stories built from real SKUs.',
    href: '/collections/pretend-play-worlds',
    product: kitchen,
    className: 'mission-play',
  },
];

const roomPlans = {
  Nursery: {
    title: 'A giftable nursery corner',
    copy: 'Soft rocker, milestone play, and visible storage for a first birthday setup.',
    products: [hero, walker, shelf],
    palette: 'nursery',
  },
  Playroom: {
    title: 'The playroom reset',
    copy: 'A low shelf, storage bins, and an art station turn scattered toys into repeatable play.',
    products: [storage, shelf, desk],
    palette: 'playroom',
  },
  Kitchen: {
    title: 'Kitchen helper routine',
    copy: 'A learning tower connects daily parent-child routines with pretend cooking.',
    products: [tower, kitchen, mudKitchen],
    palette: 'kitchen',
  },
  Outdoor: {
    title: 'Backyard pretend play',
    copy: 'Mud kitchen and garden play cues make outdoor play feel seasonal and specific.',
    products: [mudKitchen, kitchen, walker],
    palette: 'outdoor',
  },
};

type RoomKey = keyof typeof roomPlans;
type DesignMode = 'gift' | 'room' | 'play';

const designModes: {
  id: DesignMode;
  label: string;
  icon: typeof Gift;
  kicker: string;
  headline: string;
  copy: string;
  primaryCta: string;
  primaryHref: string;
  secondaryCta: string;
  secondaryHref: string;
  heroProduct: typeof hero;
  tiles: { label: string; product: typeof hero; className: string }[];
}[] = [
  {
    id: 'gift',
    label: 'Gift Theater',
    icon: Gift,
    kicker: 'First-birthday proof wall',
    headline: 'Make the gift they never forget.',
    copy: 'A character-led Labebe shop built around plush rockers, nursery moments, and memorable milestone gifts.',
    primaryCta: 'Shop giftable rockers',
    primaryHref: '/collections/giftable-rockers',
    secondaryCta: 'View Pink Unicorn',
    secondaryHref: `/product/${hero.slug}`,
    heroProduct: hero,
    tiles: [
      { label: 'Bold character', product: crocodile, className: 'tile-crocodile' },
      { label: 'Soft nursery', product: swan, className: 'tile-swan' },
      { label: 'Woodland edit', product: fox, className: 'tile-fox' },
    ],
  },
  {
    id: 'room',
    label: 'Room Builder',
    icon: HomeIcon,
    kicker: 'Room-first planning',
    headline: 'Turn one room into a complete play system.',
    copy: 'A parent-utility direction for storage, shelves, study corners, first steps, and room-ready bundles.',
    primaryCta: 'Build a room plan',
    primaryHref: '/shop/by-room',
    secondaryCta: 'Shop storage',
    secondaryHref: '/collections/playroom-reset',
    heroProduct: storage,
    tiles: [
      { label: 'Low shelf', product: shelf, className: 'tile-storage' },
      { label: 'Study corner', product: desk, className: 'tile-desk' },
      { label: 'First steps', product: walker, className: 'tile-walker' },
    ],
  },
  {
    id: 'play',
    label: 'Play Worlds',
    icon: Paintbrush,
    kicker: 'Pretend-play scene shop',
    headline: 'Build the tiny world before choosing the toy.',
    copy: 'A cinematic product-world direction for kitchens, cafes, laundry day, garden play, and creative corners.',
    primaryCta: 'Explore play worlds',
    primaryHref: '/collections/pretend-play-worlds',
    secondaryCta: 'View play kitchen',
    secondaryHref: `/product/${kitchen.slug}`,
    heroProduct: kitchen,
    tiles: [
      { label: 'Cafe counter', product: products['kids-coffee-shop-grocery-store-playset'], className: 'tile-cafe' },
      { label: 'Laundry day', product: products['wooden-washer-dryer-playset'], className: 'tile-laundry' },
      { label: 'Garden scene', product: mudKitchen, className: 'tile-garden' },
    ],
  },
];

export default function Home() {
  const [age, setAge] = useState('1-3Y');
  const [room, setRoom] = useState('Nursery');
  const [occasion, setOccasion] = useState('First Birthday');
  const [activeRoom, setActiveRoom] = useState<RoomKey>('Playroom');
  const [activeDesign, setActiveDesign] = useState<DesignMode>('gift');

  const bestSellers = getBestSellers().slice(0, 8);
  const recommendations = giftFinderRecommendations(age, room, occasion);
  const plan = roomPlans[activeRoom];
  const design = designModes.find((mode) => mode.id === activeDesign) ?? designModes[0];

  const commerceStats = useMemo(() => {
    const reviewBacked = productList.filter((product) => product.reviewCount !== null).length;
    const rooms = new Set(productList.flatMap((product) => product.roomTags)).size;
    return [
      ['Age', 'stage-first paths for faster gift decisions'],
      [String(reviewBacked), 'products with visible parent review signals'],
      [String(rooms), 'room paths for practical home planning'],
    ];
  }, []);

  return (
    <div className={`labebe-home commerce-redesign design-${activeDesign}`}>
      <div className="design-switch-shell" aria-label="Design direction switcher">
        <div className="container design-switch">
          {designModes.map(({ id, label, icon: Icon }) => (
            <button
              className={activeDesign === id ? 'active' : ''}
              key={id}
              onClick={() => setActiveDesign(id)}
              type="button"
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </div>
      </div>

      <section className="commerce-hero" aria-label="Labebe commerce hero">
        <div className="container commerce-hero-grid">
          <div className="hero-copy-block">
            <span className="site-kicker">
              <Sparkles size={16} />
              {design.kicker}
            </span>
            <h1>{design.headline}</h1>
            <p>{design.copy}</p>
            <div className="hero-actions">
              <Link to={design.primaryHref} className="primary-action">
                {design.primaryCta}
                <ArrowRight size={17} />
              </Link>
              <Link to={design.secondaryHref} className="secondary-action">
                {design.secondaryCta}
              </Link>
            </div>
          </div>

          <div className="product-theater" aria-label="Featured Labebe product theater">
            <Link className="theater-main" to={`/product/${design.heroProduct.slug}`}>
              <span className="floating-label">{design.label}</span>
              <img src={design.heroProduct.image} alt={design.heroProduct.title} />
              <strong>{design.heroProduct.title}</strong>
              <em>
                {formatPrice(design.heroProduct.price)}
                {design.heroProduct.reviewCount ? ` · ${design.heroProduct.reviewCount} reviews` : ''}
              </em>
            </Link>
            {design.tiles.map(({ label, product, className }) => (
              <Link className={`theater-tile ${className}`} to={`/product/${product.slug}`} key={product.slug}>
                <img src={product.image} alt={product.title} />
                <span>{label}</span>
              </Link>
            ))}
          </div>

          <div className="hero-commerce-rail" aria-label="Commerce proof points">
            {commerceStats.map(([value, label]) => (
              <div key={label}>
                <strong>{value}</strong>
                <span>{label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="container mission-section" aria-label="Primary shopper missions">
        <div className="section-heading split wide">
          <div>
            <span className="site-kicker">Start with the buying job</span>
            <h2>Shop by what the family is trying to make happen.</h2>
          </div>
          <p>
            Find a first birthday gift, reset a playroom, or build a pretend-play corner
            without starting from a long product list.
          </p>
        </div>

        <div className="mission-grid">
          {missionCards.map(({ icon: Icon, title, copy, href, product, className }) => (
            <Link className={`mission-card ${className}`} to={href} key={title}>
              <div>
                <Icon size={24} />
                <h3>{title}</h3>
                <p>{copy}</p>
                <span>
                  Shop this path
                  <MoveRight size={16} />
                </span>
              </div>
              <img src={product.image} alt={product.title} />
            </Link>
          ))}
        </div>
      </section>

      <section className="container guided-system" aria-label="Guided product finder">
        <div className="finder-copy">
          <span className="site-kicker">
            <Baby size={16} />
            Guided shopping
          </span>
          <h2>Start with one child, one room, one occasion.</h2>
          <p>
            Answer three simple prompts and get a short list of products that fit the age,
            room, and gift moment.
          </p>
        </div>

        <div className="finder-panel decision-panel">
          <ChoiceGroup label="Age" options={ageOptions} value={age} onChange={setAge} />
          <ChoiceGroup label="Room" options={roomOptions} value={room} onChange={setRoom} />
          <ChoiceGroup label="Occasion" options={occasionOptions} value={occasion} onChange={setOccasion} />

          <div className="finder-results">
            {recommendations.map((product) => (
              <Link to={`/product/${product.slug}`} key={product.slug} className="finder-result">
                <img src={product.image} alt={product.title} />
                <span>{product.world}</span>
                <strong>{product.title}</strong>
                <em>{formatPrice(product.price)}</em>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className={`room-planner-band ${plan.palette}`} aria-label="Room planner">
        <div className="container room-planner-grid">
          <div className="room-planner-copy">
            <span className="site-kicker">
              <Boxes size={16} />
              Shop by room
            </span>
            <h2>{plan.title}</h2>
            <p>{plan.copy}</p>
            <div className="room-tabs" role="tablist" aria-label="Room plans">
              {(Object.keys(roomPlans) as RoomKey[]).map((key) => (
                <button
                  className={activeRoom === key ? 'active' : ''}
                  key={key}
                  onClick={() => setActiveRoom(key)}
                  type="button"
                >
                  {key}
                </button>
              ))}
            </div>
          </div>

          <div className="room-stage">
            {plan.products.map((product, index) => (
              <Link
                className={`room-stage-product stage-${index + 1}`}
                key={product.slug}
                to={`/product/${product.slug}`}
              >
                <img src={product.image} alt={product.title} />
                <span>{product.ageRange}</span>
                <strong>{product.title}</strong>
                <em>{formatPrice(product.price)}</em>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="container collection-worlds upgraded" aria-label="Featured collections">
        <div className="section-heading split wide">
          <div>
            <span className="site-kicker">Ways to shop</span>
            <h2>Five worlds, each with its own kind of play.</h2>
          </div>
          <p>
            Start with first steps, a giftable rocker, a calm Montessori routine,
            a pretend-play world, or a playroom reset.
          </p>
        </div>

        <div className="world-grid editorial-worlds">
          {WORLDS.map((world, index) => (
            <Link to={world.href} className={`world-card world-${index + 1}`} key={world.id}>
              <img src={world.image} alt={world.name} />
              <div>
                <span>{world.productCount} products</span>
                <h3>{world.name}</h3>
                <p>{world.subtitle}</p>
                <small>{world.bestFor}</small>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="best-seller-theater" aria-label="Best seller signals">
        <div className="container section-heading split wide">
          <div>
            <span className="site-kicker">Parent favorites</span>
            <h2>Best places to start.</h2>
          </div>
          <p>
            These products have visible review-count signals and work well as the first stop
            for gifts, room planning, and pretend play.
          </p>
        </div>

        <div className="container product-grid four">
          {bestSellers.map((product) => (
            <ProductCard key={product.slug} product={product} />
          ))}
        </div>
      </section>

      <section className="container pdp-preview-section" aria-label="Product detail strategy">
        <div className="pdp-preview-copy">
          <span className="site-kicker">
            <Ruler size={16} />
            PDP that answers parent doubts
          </span>
          <h2>Everything a parent needs before adding to cart.</h2>
          <ul>
            {[
              'Age, room, and gift fit sit next to the price.',
              'Bundles connect the product to a real room moment.',
              'Care and fit notes stay close to the buying decision.',
            ].map((line) => (
              <li key={line}>
                <Check size={16} />
                {line}
              </li>
            ))}
          </ul>
          <Link to={`/product/${tower.slug}`} className="primary-action">
            See a PDP example
            <ArrowRight size={17} />
          </Link>
        </div>
        <div className="pdp-preview-stack">
          {[tower, kitchen, desk].map((product) => (
            <Link to={`/product/${product.slug}`} key={product.slug}>
              <img src={product.image} alt={product.title} />
              <span>{product.world}</span>
              <strong>{product.title}</strong>
              <em>{formatPrice(product.price)}</em>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

function ChoiceGroup({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: string[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="choice-group">
      <span>{label}</span>
      <div>
        {options.map((option) => (
          <button
            className={value === option ? 'active' : ''}
            key={option}
            onClick={() => onChange(option)}
            type="button"
          >
            {option}
          </button>
        ))}
      </div>
    </div>
  );
}
