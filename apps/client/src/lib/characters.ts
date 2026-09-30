/** Texture keys of the playable characters (atlases in assets/sprites/<key>.*). Single source for game, lab and tests. */
export const CHARACTERS = ["cat_base", "siamese_base"] as const;
export type CharacterKey = (typeof CHARACTERS)[number];

/** Standing height in px that tools/sprite_slicer.py normalises every character to (--char-height). */
export const CHAR_HEIGHT = 183;
