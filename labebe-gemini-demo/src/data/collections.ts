export type World = {
  id: string;
  name: string;
  subtitle: string;
  description: string;
  productCount: number;
  image: string;
  href: string;
  bestFor: string;
  productSlugs: string[];
};

export const WORLDS: World[] = [
  {
    id: 'first-steps-activity',
    name: 'First Steps & Activity',
    subtitle: 'Walkers, art corners, and busy little routines',
    description: 'Milestone-led products for first steps, active hands, and daily play habits.',
    productCount: 10,
    image: '/assets/products/activity-montessori-baby-push-walker.jpg',
    href: '/collections/first-steps-activity',
    bestFor: 'First birthday, early movement, active play',
    productSlugs: [
      'activity-cube-baby-push-walker',
      'activity-montessori-baby-push-walker',
      'classic-montessori-baby-push-walker',
      'ice-cream-cart-baby-push-walker',
      'farm-themed-baby-push-walker',
      'panda-baby-push-walker',
      'magnetic-easel-with-deluxe-art-supplies-pink',
    ],
  },
  {
    id: 'giftable-rockers',
    name: 'Giftable Rockers',
    subtitle: 'First rides, first birthdays, first brave moments',
    description: 'Plush and wooden rockers organized as emotional gifts, not just animal SKUs.',
    productCount: 13,
    image: '/assets/products/pink-unicorn-plush-rocker.jpg',
    href: '/collections/giftable-rockers',
    bestFor: 'First birthday, baby shower, grandparent gift',
    productSlugs: [
      'pink-unicorn-plush-rocker',
      'llama-plush-rocker',
      'crocodile-plush-rocker',
      'white-swan-plush-rocker',
      'fox-plush-rocker',
      'blue-squirrel-plush-rocker',
      'highlander-cattle-plush-rocker',
    ],
  },
  {
    id: 'montessori-at-home',
    name: 'Montessori at Home',
    subtitle: 'Kitchen helpers, low shelves, calm routines',
    description: 'Furniture-led discovery for independence, access, and daily parent-child routines.',
    productCount: 17,
    image: '/assets/products/foldable-learning-tower-montessori-kitchen-tower-log-color.jpg',
    href: '/collections/montessori-at-home',
    bestFor: 'Kitchen participation, toy rotation, independent access',
    productSlugs: [
      'foldable-learning-tower-montessori-kitchen-tower-log-color',
      'learning-tower-montessori-kitchen-tower-white',
      'natural-wood-montessori-shelf-with-storage-boxes',
    ],
  },
  {
    id: 'pretend-play-worlds',
    name: 'Tiny Pretend Worlds',
    subtitle: 'Kitchens, shops, laundry, mud play',
    description: 'Pretend-play sets merchandised as small worlds parents can imagine in the room: tiny chef, cafe play, laundry day, and garden routines.',
    productCount: 9,
    image: '/assets/products/cream-wooden-play-kitchen-set-with-storage.jpg',
    href: '/collections/pretend-play-worlds',
    bestFor: 'Tiny chef, cafe play, outdoor sensory play',
    productSlugs: [
      'cream-wooden-play-kitchen-set-with-storage',
      'midnight-serenity-wooden-play-kitchen-set',
      'kids-coffee-shop-grocery-store-playset',
    ],
  },
  {
    id: 'playroom-reset',
    name: 'Playroom Reset',
    subtitle: 'Room order without losing play',
    description: 'Storage and activity pieces merchandised by room problem: clutter, small-space corners, art corners.',
    productCount: 6,
    image: '/assets/products/natural-wood-montessori-shelf-with-storage-boxes.jpg',
    href: '/collections/playroom-reset',
    bestFor: 'Toy rotation, small rooms, activity corners',
    productSlugs: [
      'natural-wood-montessori-shelf-with-storage-boxes',
      'kids-toy-storage-organizer-bookshelf-with-bins',
      'rubber-wood-corner-cabinet',
      'children-s-writing-desk-and-chair-set-with-hutch---cork-board-for-study---art',
    ],
  },
];

export const getWorld = (id?: string) => WORLDS.find((world) => world.id === id);
