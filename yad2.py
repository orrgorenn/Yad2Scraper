import argparse
import datetime

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

    print(f"Starting scraping: {datetime.datetime.now()}")
    logic.get_data()
