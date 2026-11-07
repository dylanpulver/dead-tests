require "minitest/autorun"

class ThingTest < Minitest::Test
  def setup
    @thing = Thing.new
  end

  def test_it_works
    assert_equal 1, build_widget.value
  end

  # TRUE POSITIVE: asserts, not named test_, nobody calls it
  def verifies_the_fallback
    assert_nil @thing.fallback
    refute @thing.broken?
  end

  # NOT a hit: a helper called from the live test above
  def build_widget
    assert @thing
    @thing
  end

  # NOT a hit: deliberately parked
  def disabled_test_old_behaviour
    assert false
  end

  def teardown
    @thing = nil
  end
end
