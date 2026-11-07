class SharedTest < ActiveSupport::TestCase
  # NOT a hit: called from helper_user_test.rb (cross-file helper)
  def shared_expectation
    assert true
  end

  def test_real
    assert true
  end
end
