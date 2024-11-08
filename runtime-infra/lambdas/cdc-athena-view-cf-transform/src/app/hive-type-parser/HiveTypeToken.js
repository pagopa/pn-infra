const PUNCTUATION = [ "<", ">", ",", ":" ];
const KEYWORDS = [ "array", "struct" ];
const FIXED_TOKENS = [ ... PUNCTUATION, ... KEYWORDS ];



export class HiveTypeToken {
  #value;
  #position;
  #isFixed;
  #type;

  constructor( value, position ) {
    this.#value = value;
    this.#position = position;
    this.#isFixed = FIXED_TOKENS.includes( value )
    this.#type = (this.#isFixed ? "FIXED" + value : "WORD" )

  }

  toString() {
    return `Token(type=${this.#type},value=${this.#value},position=${this.#position})`
  }

  get value() {
    return this.#value
  }

  get position() {
    return this.#position
  }

  get isFixed() {
    return this.#isFixed
  }

  get type() {
    return this.#type
  }

}

HiveTypeToken.PUNCTUATION = PUNCTUATION
