import argparse

from logic import Yad2Logic

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-c",
        "--city_code",
        help="Enter city code.",
        default=8300,
        type=int
    )

    args = parser.parse_args()

    logic = Yad2Logic(args.city_code)

    logic.get_data()
